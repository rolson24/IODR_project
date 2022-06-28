from dash import Dash, dcc, html, Input, Output, State, callback_context
from plotly.subplots import make_subplots
from whitenoise import WhiteNoise

import numpy as np
import pandas as pd
import urllib.request
import requests
import json
import io
import plotly.graph_objects as go
import plotly.express as px

from rq import Queue
from worker import conn

import logging
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from scipy.stats import linregress
from scipy import stats


def get_OD_dataframe(device, chIDs, readAPIkeys):
    """Returns a tuple of dataframes from Thingspeak containing the OD data for the specified device.

    return value 0 is the dataframe containing OD data for all tubes. Data older than two hours has been thinned.
    return value 1 is the full dataframe containing the last 8000 time points

    Arguments:

    device -- int device number (0-2)

    chIDs --  list of channel IDs from main file

    readAPIkeys -- list of API keys from main file
    """
    # select the channel ID and read API key depending on which device is being used
    # chID = chIDs[devNum-1]
    chID = chIDs[device]

    # readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[device]

    # get data from Thingspeak
    myUrl = f'https://api.thingspeak.com/channels/{chID}/feeds.csv?results=8000'
    # myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    # print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
    # print("the first df", df)

    df2 = df.drop('entry_id', axis='columns')

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')

    # remove the created_at column
    df3 = df2.drop('created_at', axis='columns')

    # set index to time
    df4 = df3.set_index('time')




    # print("df8 ", df8)
    full_dataframe = df4

    return full_dataframe

def cull_data(dataframe):
    first_time_time = dataframe.index[0]
    last_time_time = dataframe.index[-1]
    # print("first time ", first_time_time)
    # print("last time ", last_time_time)

    df5 = dataframe.loc[(dataframe.index > (last_time_time - pd.Timedelta(2, 'h'))) & (dataframe.index < last_time_time)]

    df6 = dataframe.loc[(dataframe.index > first_time_time) & (dataframe.index < last_time_time - pd.Timedelta(2, 'h'))]
    df7 = df6.iloc[::10]

    selected_dataframe = pd.concat([df7, df5])
    return selected_dataframe

# Not being used
def format_OD_data(dataframe):
    """Returns a dataframe with the index set as the time (in datetime objects)

    Arguments:

    dataframe -- pandas dataframe directly from Thingspeak with 'created_at' column as strings formatted for time
    """
    df2 = dataframe.drop('entry_id', axis='columns')
    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df3 = df2.drop('created_at', axis='columns')
    df4 = df3.set_index('time')
    # print(df4.head())
    return df4


def rename_tubes(dataframe, newNames):
    """Modifies the input dataframe inplace to rename the columns to the newNames list
    List must be the same length and order as the columns you want to rename

    Arguments:

    dataframe -- pandas dataframe with the columns being the OD data of the tubes and the names of the columns being
    the name of each tube

    newNames -- list of names to rename the columns to. (must be in the order of how you want them renamed)
    """
    # rename tubes on update
    i = 0
    # print("rename df", dataframe)
    for col in dataframe.columns:
        dataframe.rename(columns={col: newNames[i]}, inplace=True)
        # print(newNames[i])
        i += 1

    return


def get_temp_data(device, chIDs, readAPIkeys):
    """Returns a tuple of pandas dataframes containing the temperature data for the specified device with columns
    Temp Int and Temp Ext

    return value 0 is dataframe with older data having been thinned
    value 1 is the full dataframe containing about the last 1500 data points

    Arguments:
    device -- int device number (0-2)

    chIDs --  list of channel IDs from main file

    readAPIkeys -- list of API keys from main file
    """
    # select the channel ID and read API key for temperature data
    chID = chIDs[3]

    # readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[3]

    # get data from Thingspeak
    myUrl = f'https://api.thingspeak.com/channels/{chID}/feeds.csv?results=8000'
    # myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    # print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))

    df2 = df.drop('entry_id', axis='columns')

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df2 = df2.drop('created_at', axis='columns')
    df2.set_index('time', inplace=True)

    # format data for temperature, inlcude only temperature that matches the device selected
    if (device == 0):
        df3 = df2.drop(['field3', 'field4', 'field5', 'field6'], axis='columns')
    elif (device == 1):
        df3 = df2.drop(['field1', 'field2', 'field5', 'field6'], axis='columns')
    else:
        df3 = df2.drop(['field1', 'field2', 'field3', 'field4'], axis='columns')

    # rename columns for graphing
    tempNames = {
        'field1': 'Temp Int',
        'field2': 'Temp Ext',
        'field3': 'Temp Int',
        'field4': 'Temp Ext',
        'field5': 'Temp Int',
        'field6': 'Temp Ext'
    }
    df3.rename(columns=tempNames, inplace=True)

    first_time_time = df3.index[0]
    last_time_time = df3.index[-1]
    # print("first time ", first_time_time)
    # print("last time ", last_time_time)

    full_dataframe = df3

    return full_dataframe


def format_ln_data(dataframe, tube_num, offset_value=0):
    """Returns a pandas dataframe with columns OD and lnOD (log transformed data), index is the time values

    Arguments:

    dataframe -- pandas dataframe with time

    tube_num -- number (int) of which tube to get data on

    offset_value -- number for offset of OD data (default 0)
    """
    # print("ln dataframe", dataframe.head())
    # get the name of the tube
    tube_name = dataframe.columns[tube_num]

    # create new dataframe with tube_names and time index
    df2 = dataframe.loc[:, [tube_name]].dropna()
    # print(df2.head())

    # rename tube column to OD
    df2.rename({tube_name: 'OD'}, axis=1, inplace=True)
    df2['OD'] = df2['OD'] + offset_value
    # print("OD after blank val sub", df2['OD'])
    # calculate the natural log
    df2['lnOD'] = np.log(df2['OD'])
    # print(df2['lnOD'])

    return df2


