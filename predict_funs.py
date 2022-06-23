def predict_curve(dataframe, data_range):
    """Returns a tuple of the list of curve information and the last collected data point for displaying the curve

    Arguements:

    dataframe -- pandas dataframe with columns 'OD' and 'lnOD' that comes from function 'format_ln_data'

    data_range -- list of two values for the range of data to use for curve estimation
    """
    # copy the dataframe so not editing in place
    df = dataframe.copy()
    # change the index (time) to an hour number
    df.index = (df.index - df.index[0]) / pd.Timedelta(1, 'h')  # this is done here so data gets displayed in datetime
    # get the last time point in a float while here for displaying prediction
    last_time_point = df.index[-1]
    # print(f"last time point val: {last_time_point}")
    # print(f"slider val: {slider_vals}")
    # filter data so that only the data within the range is used
    df2 = df.loc[(df.index > (last_time_point + data_range[0])) & (df.index < last_time_point + data_range[1])]
    df2.dropna(inplace=True)

    print("begin selection: ", (last_time_point + data_range[0]))
    print("end selection: ", last_time_point + data_range[1])

    print("cleaned lnOD ")
    print("df2", df2)
    curve_info = [0, 0, 0]
    if len(df2['lnOD']) > 2:    # makes sure the dataframe is not empty, linregress needs > 2 datapoints
        # do the curve fit
        # popt, pcov = curve_fit(curve, df2.index, df2['lnOD']) # used if using a different estimate curve than linregress
        curve_info[0], curve_info[1], curve_info[2], p, se = linregress(df2.index, df2['lnOD'])
        # print("popt", popt)
        print("slope, intercept: ", curve_info)
    else:
        print('no data')
        # popt = np.array([])  # need to figure out what this should actually be
        curve_info = []
        r = 0
    return curve_info, last_time_point


def linear_curve(t, a, b):
    """
    fit data to linear model
    """
    return a * t + b


# move to functions file
def estimate_times(lnDataframes, target_vals):
    """Returns a tuple of a list of time estimates (strings) and a list of r_values from the prediction curves (ints)

    Arguments:

    lnDataframes -- list of dataframes stored in json files containing the columns 'OD' and 'lnOD' with the index being
    datetime objects, returned from the format_ln_data function

    target_vals -- list of target OD values to make estimates for, must be in the same order of the lnDataframes
    """
    r_vals = []
    estimates = []
    for i in range(len(lnDataframes)):
        # get the data from json file
        lnODdf = pd.read_json(lnDataframes[i], orient='table')
        print("lnODdf",  lnODdf)
        curve_info, last_time_point = predict_curve(lnODdf, [-2, 0])    # get the prediction info

        if len(curve_info) != 0:

            first_time_time = lnODdf.index[0]
            # last_time_time = lnODdf.index[-1]

            # get where the ln curve intercepts the target line
            intercept_x = (np.log(float(target_vals[i])) - curve_info[1]) / curve_info[0]  # solve for x = (y - b)/slope
            # transform from float value intercept to datetime object
            time_intercept_x = (intercept_x * pd.Timedelta(1, 'h')) + first_time_time
            time_intercept_x_str = (time_intercept_x).strftime("%Y-%m-%d %H:%M:%S")     # from datetime object to string

            estimates.append(time_intercept_x_str)
            r = curve_info[2]
            r_vals.append(round(r**2, 3))     # append r^2 values

        else:
            estimates.append("none")
            r_vals.append(0)
    return estimates, r_vals

