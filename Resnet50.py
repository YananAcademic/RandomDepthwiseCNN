This is write by Keras, you can also train your own Resnet50 net work 
from keras import backend as K
from keras.models import Model
from keras.layers import Dense, Input, GlobalAveragePooling2D,Dropout
from keras.preprocessing.image import ImageDataGenerator
from keras.callbacks import ModelCheckpoint, ReduceLROnPlateau
from keras.applications import ResNet50, DenseNet201

import pandas as pd
import numpy as np

import preprocess_crop
from keras.preprocessing.image import ImageDataGenerator
from keras.applications.inception_v3 import preprocess_input

data_gen_args = dict(rotation_range=30,
                width_shift_range=0.05,
                height_shift_range=0.05,
                shear_range=0.05,
                zoom_range=0.05,
                horizontal_flip=True,
                fill_mode='nearest')

def adjustData(img):
    if(np.max(img[0]) > 1):
        img[0] = img[0] / 255
        img[0] = np.repeat(img[0], 3, axis=3)
    return img

def generate_data(batch_size,img_path,mask_path,benign_folder,malignant_folder,aug_dict,
                    class_mode = "binary", shuffle = True, image_color_mode = "grayscale",
                    mask_color_mode = "grayscale",image_save_prefix  = "image_aug",mask_save_prefix  = "mask_aug",
                    flag_multi_class = False,num_class = 2,save_to_dir = None,target_size = (256,256),seed = 1):
    image_datagen = ImageDataGenerator(**data_gen_args)
    mask_datagen = ImageDataGenerator(**data_gen_args)
    image_generator = image_datagen.flow_from_directory(
        img_path,
        classes = [benign_folder,malignant_folder],
        class_mode = class_mode,
        color_mode = image_color_mode,
        shuffle = shuffle,
        target_size = target_size,
        batch_size = batch_size,
        save_to_dir = save_to_dir,
        save_prefix  = image_save_prefix,
        seed = seed)
    mask_generator = mask_datagen.flow_from_directory(
        mask_path,
        classes = [benign_folder,malignant_folder],
        class_mode = class_mode,
        color_mode = mask_color_mode,
        shuffle = shuffle,
        target_size = target_size,
        batch_size = batch_size,
        save_to_dir = save_to_dir,
        save_prefix  = mask_save_prefix,
        seed = seed)

    if(class_mode is None):
        for img in image_generator:
            if(np.max(img) > 1):
                img = img / 255
            img = np.repeat(img, 3, axis=3)
            yield img
    else:
        for img in image_generator:
            yield adjustData(list(img))


def random_crop(img, random_crop_size):
    # Note: image_data_format is 'channel_last'
    assert img.shape[2] == 3
    height, width = img.shape[0], img.shape[1]
    dy, dx = random_crop_size
    x = np.random.randint(0, width - dx + 1)
    y = np.random.randint(0, height - dy + 1)
    return img[y:(y+dy), x:(x+dx), :]


def crop_generator(batches, crop_length):
    """Take as input a Keras ImageGen (Iterator) and generate random
    crops from the image batches generated by the original iterator.
    """
    while True:
        batch_x, batch_y = next(batches)
        batch_crops = np.zeros((batch_x.shape[0], crop_length, crop_length, 3))
        for i in range(batch_x.shape[0]):
            batch_crops[i] = random_crop(batch_x[i], (crop_length, crop_length))
        yield (batch_crops, batch_y)

def build_net(inputs_shape):
    conv_base = ResNet50(weights=None,
                  include_top=False,
                  input_shape=inputs_shape)
    '''
    conv_base = DenseNet201 (weights='imagenet',
                  include_top=False,
                  input_shape=inputs_shape)

    pool1 = GlobalAveragePooling2D()(conv_base.output)
    dense2 = Dense(1, activation='sigmoid')(pool1)
    model = Model(inputs=conv_base.input, outputs= dense2)
    '''
    pool1 = GlobalAveragePooling2D()(conv_base.output)
    #drop1 = Dropout(0.9)(pool1)
    predictions = Dense(7, activation= 'softmax')(pool1)
    #predictions = Dense(1, activation= 'sigmoid')(drop1)
    model = Model(inputs=conv_base.input, outputs= predictions)
    return model


if __name__ == '__main__':
    
    #image_size = (600, 450)
    crop_lenght = 400
    crop_width = 400
    crop_size = (crop_lenght, crop_width)

    train_datagen = ImageDataGenerator(
         rescale=1./255,
         rotation_range=20,
         width_shift_range=0.05,
         height_shift_range=0.05,
         shear_range=0.05,
         zoom_range=0.05,
         horizontal_flip=True,
         fill_mode='nearest')
        
    val_datagen = ImageDataGenerator(rescale=1./255)
    test_datagen = ImageDataGenerator(rescale=1./255)

    train_gen = train_datagen.flow_from_directory(
        'train',
        target_size= crop_size,
        batch_size=32,
        class_mode='categorical',
        interpolation = 'lanczos:center')
    #train_gen=crop_generator(train_gen, crop_lenght)

    '''
    val_gen = val_datagen.flow_from_directory(
        'val',
        target_size=crop_size,
        batch_size=18,
        class_mode='categorical',
        interpolation = 'lanczos:center')
    #val_gen=crop_generator(val_gen, crop_lenght)
    '''
    test_gen = test_datagen.flow_from_directory(
        'test',
        target_size=crop_size,
        batch_size=18,
        class_mode='categorical',
        interpolation = 'lanczos:center')
    #test_gen = crop_generator(test_gen, crop_lenght)
        
    K.clear_session()
    model = build_net(crop_size+(3,))
    #model.summary()

    model.compile(optimizer='adam',loss='binary_crossentropy',metrics=['accuracy'])

    m_index = 0
    path_model = 'model_res/res%s.h5' % (m_index)
    callbacks_list = [
        ModelCheckpoint(
            filepath = path_model,
            monitor='acc',
            save_best_only=True,
            verbose = 1
        ),
        ReduceLROnPlateau(
            monitor='loss', 
            factor=0.2,
            patience=5,
            min_lr=1e-5,
            verbose = 1
        )
    ]
    
    historyf = model.fit_generator(
                        train_gen,
                        steps_per_epoch=4,
                        epochs=100,
                        verbose=1,
                        callbacks=callbacks_list,
                        validation_data=None,
                        validation_steps=1)

    results = model.evaluate_generator(test_gen, steps=1)
    
    result1 = model.predict_generator(test_gen, steps=1)
    print(result1)
    
    '''
    #csvdata=[['image', 'true_label','pred_label']]
    #sourceDir = "/research/datasci/fgf4/ISIC2018/test"

    
    for x in result1: 
       csvdata.append([x,str(test_gen),str(np.argmax(result1))])
       
    with open("/research/datasci/fgf4/ISIC2018/"+'predict1.csv', 'w') as csvFile:
        writer = csv.writer(csvFile)
        writer.writerows(csvdata)
    csvFile.close()
    '''
    
    
    hdict = historyf.history
    hdict.keys()
    loss_train = hdict['loss']
    loss_val = hdict['val_loss']
    acc_train = hdict['acc']
    acc_val = hdict['val_acc']
    df = pd.DataFrame({'loss':loss_train, 'val_loss':loss_val,'acc':acc_train, 'vacc':acc_val})
    #df = pd.DataFrame({'loss':loss_train, 'acc':acc_train})
    path = 'model_res/model_%s_loss' % m_index
    df.to_csv(path+'.csv', index = False)
    
    results = model_saved.evaluate_generator(test_gen, steps=1)
    print(results)
