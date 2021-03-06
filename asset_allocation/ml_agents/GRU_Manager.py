'''
Tensorflow GRU-RNN Portfolio Manager
'''


import numpy as np
import pandas as pd
from scipy.special import softmax
import matplotlib.pyplot as plt

import tensorflow as tf
tf.get_logger().setLevel('WARNING')


class GRU_Manager:

    def __init__(self, df,data_name, batch_size=256,
                 epochs=200, buffer=10000,
                 hidden_units=None, load_last=True
                 ):

        self.stocks = df.copy()
        self.name=data_name

        #Hyperparameter settings
        TRAIN_SIZE = int(0.80*len(self.stocks.index))
        VALID_SIZE = int(0.20*len(self.stocks.index))
        self.BATCH_SIZE = batch_size
        self.BUFFER_SIZE = buffer
        self.EPOCHS = epochs
        self.EPOCH_TRAIN_STEPS = TRAIN_SIZE/self.BATCH_SIZE
        self.EPOCH_VALID_STEPS = VALID_SIZE/self.BATCH_SIZE


        #processing data
        self.X_train, self.y_train = self._process_data(self.stocks,end_index=TRAIN_SIZE)
        self.X_val, self.y_val = self._process_data(self.stocks,start_index=TRAIN_SIZE)

        self.train_data = self._convert_to_tensor(self.X_train, self.y_train)
        self.val_data = self._convert_to_tensor(self.X_val, self.y_val, validation_data=True)

        #set hidden units based on data input size and output size
        if hidden_units == None:
            inpt = self.X_train.shape[-2:]
            hidden_units = int((2/3)*(inpt[0]*inpt[1]+self.y_val.shape[-1:][0]))

        #loading previously trained model, training a new model if none exist
        if load_last:
            try:
                self.model = tf.keras.models.load_model('./models/saved_model'+self.name)
                print('...Loaded model')

            except Exception as e:
                print('COULD NOT LOAD MODEL: Exception '+str(e))
                self.model, self.history = self._build_fit_save(hidden_units)
                self.plot_train_history()
        else: 
            self.model, self.history = self._build_fit_save(hidden_units)
            self.plot_train_history()

    #-----------------------------------------------------#
    #                  Data Processing Funcs              #       
    #-----------------------------------------------------#

    def _process_data(self, df, start_index=1, end_index=None, history_size = 5,step = 1):
  
        if not isinstance(df, pd.DataFrame):
            raise ValueError("data must be of type pandas.DataFrame")

        x = []
        y = []

        #time t-history size 
        start_index = start_index+history_size
        if end_index is None:
            end_index = len(df.index)-1

        #window slices of data
        for i in range(start_index, end_index):
            indices = range(i-history_size, i, step)
            x.append(df.iloc[indices].to_numpy())
            y.append(df.iloc[i].to_numpy())

        return np.array(x), np.array(y)        

    def _convert_to_tensor(self, X, y, validation_data=False):

        if not isinstance(X, np.ndarray):
            raise ValueError("Error in data processing. Not of type numpy.ndArray")
        
        data = None

        if not validation_data:
            data = tf.data.Dataset.from_tensor_slices((X,y))
            data = data.cache().shuffle(self.BUFFER_SIZE).batch(self.BATCH_SIZE).repeat()
        else:
            data = tf.data.Dataset.from_tensor_slices((X, y))
            data = data.batch(self.BATCH_SIZE).repeat()
        return data

    #-----------------------------------------------------#
    #                  ML Model Functions                 #       
    #-----------------------------------------------------#

    def _build_model(self, units):
        #building a two stakced GRU with fully connected layer model
        model = tf.keras.models.Sequential()
        model.add(tf.keras.layers.GRU(units,
                                      input_shape=self.X_train.shape[-2:],
                                      activation='relu',
                                      return_sequences=True))
        model.add(tf.keras.layers.GRU(int(units/2),
                                      activation='relu'))
        model.add(tf.keras.layers.Dense(self.y_val.shape[-1:][0]))
        model.compile(optimizer=tf.keras.optimizers.RMSprop(), loss='mse', metrics=['accuracy'])
        model.summary()

        return model

    def _build_fit_save(self,units):
        model = self._build_model(units)
        history = model.fit(self.train_data, 
                                      epochs=self.EPOCHS,
                                      steps_per_epoch=self.EPOCH_TRAIN_STEPS,
                                      validation_data=self.val_data,
                                      validation_steps=self.EPOCH_VALID_STEPS,
                                      verbose=0
                                      )
        model.save('./models/saved_model'+self.name)

        return model, history

    #-----------------------------------------------------#
    #                  Plotting Functions                 #       
    #-----------------------------------------------------#

    def plot_train_history(self):
        loss = self.history.history['loss']
        val_loss = self.history.history['val_loss']

        epochs = np.arange(len(loss))
        
        plt.figure()

        plt.plot(epochs, loss, 'b', label='Training loss')
        plt.plot(epochs, val_loss, 'r', label='Validation loss')
        plt.title("GRU-RNN")
        plt.legend()

        plt.show()

    def get_weights(self,pred_df):
        #creating weights from prediction using softmax
        weights = pd.DataFrame(pred_df.iloc[0])
        weights.columns = ['Weights']
        
        tmp = weights['Weights'].values
        tmp[tmp<0]=0
        weights['Weights'] = softmax(np.log(tmp))
        weights = weights.reset_index()
        weights = weights.rename(columns={'index':'Stocks'})
        return weights

    def save_true_and_predicted(self):
        #saving true prices, prediction of prices, and weights
        for x,y in self.val_data.take(1):
            
            true_df = pd.DataFrame(y.numpy(), columns=self.stocks.columns)
            pred_df = pd.DataFrame(self.model.predict(x), columns=self.stocks.columns)
            weights = self.get_weights(pred_df)
        true_df.to_csv('./ml_data/'+self.name+'_true.csv',index=False)
        pred_df.to_csv('./ml_data/'+self.name+'_gru_predicted.csv',index=False)
        weights.to_csv('./portfolio_data/'+self.name+'_gru_weights.csv',index=False)
        

