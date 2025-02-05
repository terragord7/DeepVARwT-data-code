1  #!/usr/bin/env python36
2  # -*- coding: utf-8 -*-

import numpy as np
import torch
from custom_loss import *
from seed import *
import math
from lstm_network import DeepVARwT



def get_t_function_values_(sample_size):
    r"""
        Get values of time functions.
        Parameters
        ----------
        sample_size
           description: the length of time series
           type: int
           shape: T

        Returns
        -------
        time_functions_array
           description: array of time function values
           type: array
           shape: (3,T)
     """

    time_functions_array = np.zeros(shape=(3, sample_size))
    t = (np.arange(sample_size) + 1) / sample_size
    time_functions_array[0, :] = t
    time_functions_array[1, :] = t * t
    time_functions_array[2, :] = t * t * t

    return time_functions_array



def get_data_and_time_function_values(train_data):
    r"""
        Prepare time function values and data for neural network training.
        Parameters
        ----------
        train_data
           description: training data
           type: dataframe
           shape: (T,m+1)

        Returns
        -------
        data_and_t_function_values
           description: the observations of multivariate time series and values of time functions
           type: dict
    """
    seq_len=train_data.shape[0]
    train_data_and_t_function_values={}
    time_functions_array=get_t_function_values_(seq_len)
    time_functions_temp=time_functions_array

    time_functions_array1=time_functions_temp.transpose().tolist()
    time_functions=[]
    time_functions.append(time_functions_array1)
    time_func_array= np.array(time_functions)
    # the original shape of time functions array: (seq=T,input_size=6)
    # here we need to change the shape of which to(batch=1,sep=T,input_size=6)
    train_data_and_t_function_values['t_functions'] = torch.from_numpy(time_func_array)
    #observations shape(T,m)
    observations=train_data.iloc[:,1:]
    observations_array=np.array(observations)
    train_data_and_t_function_values['multi_target'] = torch.from_numpy(observations_array)

    return train_data_and_t_function_values





def change_data_shape(original_data):
    r"""
        Change shape of data.
        Parameters
        ----------
        original_data
           description: the original data
           type: tensor
           shape: (batch,seq,input)

        Returns
        -------
        transformed data 
           description: transformed data
           type: tensor
           shape: (seq,batch,input)
    """
    #change to numpy from tensor
    original_data=original_data.numpy()
    new_data=[]
    for seq_temp in range(original_data.shape[1]):
        new_data.append(original_data[:,seq_temp,:].tolist())
    #change to tensor
    new_data=torch.from_numpy(np.array(new_data))
    return new_data


def plot_estimated_trend(m,df_trend,df_ts,estimated_trend_file_path):
    r"""
        Plot estimated trends and observations.
        Parameters
        ----------
        df_trend
           description: estimated trends
           type: dataframe
           shape: (T,m)

        df_ts
           description: observations
           type: dataframe
           shape: (T,m)  

        estimated_trend_file_path
           description: path for saving estimated trends
           type: str                 

        Returns
        -------
    """

    import matplotlib.pyplot as plt
    if (len(df_ts.columns)) % 2 != 0:
        n_rows = int(len(df_ts.columns) / 2) + 1
    else:
        n_rows = int(len(df_ts.columns) / 2)
    fig, axes = plt.subplots(nrows=n_rows, ncols=2, dpi=150, figsize=(10, 10))
    for i, (col, ax) in enumerate(zip(df_ts.columns, axes.flatten())):
        df_ts.iloc[:, i].plot(legend=True, ax=ax, label='time series').autoscale(axis='x', tight=True)
        df_trend.iloc[:, i].plot(legend=True, ax=ax, label='trend');
        ax.set_title(str(col) + ": Time series vs Trend")
        ax.xaxis.set_ticks_position('none')
        ax.yaxis.set_ticks_position('none')
        ax.spines["top"].set_alpha(0)
        ax.tick_params(labelsize=6)
    plt.tight_layout();
    fig.savefig(estimated_trend_file_path+'estimated_trend.png')
    plt.close()


def print_AR_params(var_coeffs, residual_parameters,m,order):

    r"""
        Print estimated AR parameters
        Parameters
        ----------
        var_coeffs
           description: VAR coefficients generated from LSTM
           type: tensor

        residual_parameters
           description: residual parameters generated from LSTM
           type: tensor   
           
        m
           description: number of time series
           type: int      

         order
           description: order of VAR model
           type: int                

        Returns
        -------
    """


    var_cov_innovations_varp = make_var_cov_matrix_for_innovation_of_varp(residual_parameters, m, order)
    all_stationary_coeffs = A_coeffs_for_causal_VAR(var_coeffs, order, m, var_cov_innovations_varp)
    for i in range(order):
        print(all_stationary_coeffs[:, :, i])



def train_network(train_data,filtered_data,num_layers,hidden_dim,iterations_trend,iterations_AR,m,order,lr,lr_trend,res_saving_path,threshould):
    r"""
        Network training.
        Parameters
        ----------
        train_data
           description: training data
           type: dataframe
           shape: (T,m+1)

        filtered_data
           description: filtered data from a two-sided filter for OLS in Phase1
           type: dataframe
           shape: (T-8*2,m+1)

        num_layers
           description: number of LSTM network layer
           type: int

        iterations_trend
           description: number of iterations  for trend estimation in Phase 1
           type: int

        iterations_AR
           description: number of iterations for trend  and AR parameter estimation in Phase 2
           type: int

        lr
           description: learning rate for trend estimation in Phase 1  and for AR parameter estimation in Phase 2
           type: int      

        lr_trend
           description: learning rate in Phase 2 for trend estimation
           type: int

        m
           description: number of time series
           type: int      

         order
           description: order of VAR model
           type: int           

        res_saving_path
           description: the path for saving estimetd results
           type: str


        Returns
        -------
        pretrained_model
           description: pretrained model
    """
    

    data_and_t_function_values = get_data_and_time_function_values(train_data)
    #x:shape(batch=1,T,input_size=6)
    x = data_and_t_function_values['t_functions']
    #y:shape(T,m)
    y = data_and_t_function_values['multi_target']
    lstm_model = DeepVARwT(input_size=x.shape[2],
                          hidden_dim=hidden_dim,
                          num_layers=num_layers,
                          seqence_len=x.shape[1],
                           m=m,
                           order=order)
    lstm_model = lstm_model.float()
    optimizer = torch.optim.Adam(lstm_model.parameters(),lr=lr)
    log_likelihood=[]
    loss_trend=[]
    count_temp=1
    x_input = change_data_shape(x)
    import os
    #create folder for saving estimated trend
    estimated_trend_file_path = res_saving_path+ 'trend/'
    trend_folder = os.path.exists(estimated_trend_file_path)
    if not trend_folder:  # 
        os.makedirs(estimated_trend_file_path)

    #create folder for saving estimated trends
    pretrained_model_file_path = res_saving_path + 'pretrained_model/'
    pretrained_model_folder = os.path.exists(pretrained_model_file_path)
    if not pretrained_model_folder:  # 
        os.makedirs(pretrained_model_file_path)

#prepare data for plotting estiamted trends and observations
    ts_list = []
    for n in range(y.shape[1]):
        ts = y[:, n]
        ts_flatten = torch.flatten(ts)
        ts_list.append(ts_flatten.tolist())
    import pandas as pd
    df_ts = pd.DataFrame(np.transpose(np.array(ts_list)))
#filtered data
    df_filtered_ts=filtered_data.iloc[:,1:]
    filtered_trend=torch.from_numpy(np.array(filtered_data.iloc[:,1:]))
    for iter in range(0,iterations_trend):
        count_temp = 1 + count_temp
        var_coeffs, residual_parameters, trend = lstm_model(x_input.float())
        trend_part=trend[8:158,:,:]
        trend_error = compute_error_for_trend_estimation(target=filtered_trend.float(),
                                                   trend=trend_part)
        optimizer.zero_grad()
        trend_error.backward()
        optimizer.step()
        print('iterations' + str(iter+1) + ':trend error')
        print(trend_error)
        loss_trend.append(trend_error.detach().numpy())
    #save trend estimation loss
    loss_pd= pd.DataFrame({'trend_loss':loss_trend})
    loss_pd.to_csv(estimated_trend_file_path+'trend_loss.csv')


    lstm_model.lstm.weight_ih_l0.requires_grad = True
    lstm_model.lstm.weight_hh_l0.requires_grad = True
    lstm_model.lstm.bias_ih_l0.requires_grad = True
    lstm_model.lstm.bias_hh_l0.requires_grad = True
    lstm_model.add_trend.weight.requires_grad = True
    lstm_model.add_trend.bias.requires_grad = True
    lstm_model.init_ar_parameters.requires_grad=True
    lstm_model.init_residual_params.requires_grad=True

    optimizer = torch.optim.Adam([{'params': lstm_model.lstm.weight_ih_l0,'lr': lr_trend},
        {'params': lstm_model.lstm.weight_hh_l0, 'lr': lr_trend},{'params': lstm_model.lstm.bias_ih_l0,'lr': lr_trend},
        {'params': lstm_model.lstm.bias_hh_l0, 'lr': lr_trend},{'params': lstm_model.add_trend.weight,'lr': lr_trend},
        {'params': lstm_model.add_trend.bias, 'lr': lr_trend},{'params': lstm_model.init_ar_parameters,'lr': lr},
        {'params': lstm_model.init_residual_params, 'lr': lr}])


    for i in range(iterations_AR):
        var_coeffs, residual_parameters,trend= lstm_model(x_input.float())
        likelihood_loss = compute_log_likelihood(target=y.float(),
                                                var_coeffs=var_coeffs.float(),
                                                residual_parameters=residual_parameters,
                                                m=m,
                                                order=order,
                                                trend=trend)
        optimizer.zero_grad()
        likelihood_loss.backward()
        optimizer.step()
        print('iterations'+str(i+1)+':log-likelihood')
        print(likelihood_loss)
        log_likelihood.append(likelihood_loss.detach().numpy()[0,0])
        if i>=2:
            current_loss=log_likelihood[i]
            past1_loss=log_likelihood[i-1]
            abs_relative_error1=abs((current_loss-past1_loss)/past1_loss)
            if abs_relative_error1<threshould:
                past1_loss=log_likelihood[i-1]
                past2_loss=log_likelihood[i-2]
                abs_relative_error2=abs((past1_loss-past2_loss)/past2_loss)
                if abs_relative_error2<threshould:
                    #end loop
                    break
  


    #save loss values
    loss_pd= pd.DataFrame({'likelihood':log_likelihood})
    loss_pd.to_csv(res_saving_path+'log_likelihood_loss_phase2.csv')  
    #saving estimated trend
    trend_list = []
    for n in range(m):
        trend_flatten = torch.flatten(trend[:, :, n].t())
        trend_list.append(trend_flatten.tolist())
    df_trend = pd.DataFrame(np.transpose(np.array(trend_list))) 
    df_trend.to_csv(estimated_trend_file_path+'estimated_trend.csv')  
    #plot estimated trend
    plot_estimated_trend(m,df_trend,df_ts,estimated_trend_file_path)
    #print AR coefficients
    print_AR_params(var_coeffs, residual_parameters,m,order)
    #save pretrained-model
    model_name = pretrained_model_file_path + str(i) + '_' + 'pretrained_model.pkl'
    torch.save(lstm_model.state_dict(), model_name)

    return lstm_model

