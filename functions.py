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
    """Returns a data frame containing the OD data for the specified device.

    Arguments:
    device -- int device number (0-2)
    newNames -- list of strings for the names of each tube (expected length 8)

    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key depending on which device is being used
    # chID = chIDs[devNum-1]
    chID = chIDs[device]

    # readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[device]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=8000'.format(channel_id=chID)
    # myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    # print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))

    print("the first df", df)

    df2 = df.drop('entry_id', axis='columns')
    print(df2)
    # convert time string to datetime, and switch from UTC to Eastern time
    print(df2)
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    print(df2)
    # remove the created_at column
    df3 = df2.drop('created_at', axis='columns')
    print(df3)
    # set index to time
    df4 = df3.set_index('time')

    first_time_time = df4.index[0]
    last_time_time = df4.index[-1]
    print("df4", df4)
    print("first time ", first_time_time)
    print("last time ", last_time_time)

    df5 = df4.loc[(df4.index > (last_time_time - pd.Timedelta(2, 'h'))) & (df4.index < last_time_time)]

    df6 = df4.loc[(df4.index > first_time_time) & (df4.index < last_time_time - pd.Timedelta(2, 'h'))]
    df7 = df6.iloc[::10]

    df8 = pd.concat([df7, df5])
    print("df8 ", df8)

    return df8


# Not being used
def format_OD_data(dataframe):
    """Returns a dataframe with the time strings switched to datetime objects

    Arguments:
    dataframe -- pandas dataframe with time column as strings formatted for time
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
    dataframe -- pandas dataframe (in this context, only columns are the traces)
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
    """Returns a data frame containing the temperature data for the specified device

    Arguments:
    device -- int device number (0-2)

    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key for temperature data
    chID = chIDs[3]

    # readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[3]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=1500'.format(channel_id=chID)
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

    return df3


def format_ln_data(dataframe, tube_num, blank_value=0.01):
    """Returns a tuple of a ln transformed dataframe and the last time value
    in the dataframe as a datetime object

    Arguments:
    dataframe -- pandas dataframe with time
    """
    print("ln dataframe", dataframe.head())
    # get the name of the tube
    tube_name = dataframe.columns[tube_num]

    # create new dataframe with tube_names and time index
    df2 = dataframe.loc[:, [tube_name]].dropna()
    # df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    # df3 = df2.drop('created_at', axis = 'columns')
    # print(df2.head())
    # print(type(df2.index[0]))

    # print(df2.head())
    # df2['time'] = pd.to_timedelta(df2['created_at'])/pd.Timedelta(1, 'h')

    # rename tube column to OD
    df2.rename({tube_name: 'OD'}, axis=1, inplace=True)
    df2['OD'] = df2['OD'] - blank_value
    print("OD after blank val sub", df2['OD'])
    # calculate the natural log
    df2['lnOD'] = np.log(df2['OD'])
    # print(df2['lnOD'])
    # get rid of empty values and 0 OD values so ln is not inf
    #df2['lnOD'].replace('', np.nan, inplace=True)
    #df2['OD'].replace(0, np.nan, inplace=True)
    #df2.dropna(inplace=True)

    return df2


def predict_curve(dataframe, curve, slider_vals):
    # copy the dataframe so not editing in place
    df = dataframe.copy()
    # change the index (time) to an hour number
    df.index = (df.index - df.index[0]) / pd.Timedelta(1, 'h')  # this is done here so data gets displayed in datetime
    # get the last time point in a float while here for displaying prediction
    last_time_point = df.index[-1]
    print(f"last time point val: {last_time_point}")
    print(f"slider val: {slider_vals}")
    # filter data so that only the data within the range is used
    df2 = df.loc[(df.index > (last_time_point + slider_vals[0])) & (df.index < last_time_point + slider_vals[1])]
    df2.dropna(inplace=True)

    print("begin selection: ", (last_time_point + slider_vals[0]))
    print("end selection: ", last_time_point + slider_vals[1])

    print("cleaned lnOD ")
    print(df2)
    curve_info = [0, 0]
    if len(df2['lnOD']) > 2:
        # do the curve fit
        # popt, pcov = curve_fit(curve, df2.index, df2['lnOD'])
        curve_info[0], curve_info[1], r, p, se = linregress(df2.index, df2['lnOD'])
        # print("popt", popt)
        print("slope, intercept: ", curve_info)
    else:
        print('no data')
        # popt = np.array([])  # need to figure out what this should actually be
        curve_info = []
        r = 0
    return curve_info, last_time_point, r
