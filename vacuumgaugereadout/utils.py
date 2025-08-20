"""
Utils
=====

A list of handy functions for reading out information from the vacuum gauges
"""

import argparse as ap
import mattermostpython as mp
from . import gauges

################################################################################
def _csv_str_to_list( csv_str : str, cast_type = None  ) -> list:
    """
    Converts a string containing commas into a list. It will also cast the items 
    in the list to the specified type. This must be supplied.

    Parameters
    ==========
    csv_str : str
        The string containing commas e.g. '1,2,3'
    cast_type:
        The type you wish to cast to e.g. int

    Returns
    =======
    mylist : list
        A list of type cast_type
    """
    # No string = no list
    if csv_str == None:
        return None
    
    # No cast type = no list
    if cast_type == None:
        raise ValueError(f'ValueError: Specify a type for the list {repr(csv_str)}')
    
    # Split at the commas
    mylist = [ x.strip() for x in csv_str.split(',') ]

    # Try to cast the values
    try:
        mylist = [ cast_type(x) for x in mylist ]
        return mylist
    except Exception as e:
        raise ValueError(f"{e}\nCannot parse list {repr(csv_str)} to suggested type {cast_type}")
    

################################################################################
def _create_optimal_thresholds_from_channels( channels : list, thresholds : list ) -> list:
    """
    A function to deal with unspecified thresholds. It will throw errors if there 
    isn't a one-to-one correspondence between channels and thresholds, or it will 
    ensure that there are None's for every channel.

    Parameters
    ==========
    channels : list
        A list of channels
    thresholds : list
        A list of thresholds

    Returns
    =======
    thresholds : list
        The sanitised list of thresholds
    """
    # Possibility that no pressure thresholds specified. Ensure they are the same length with "None"
    for i in range(len(channels)):
        # First check if thresholds[i] == None -> indicates no threshold provided, convert to a list of the same length as channels
        if thresholds[i] == None:
            thresholds[i] = [None]*len(channels[i])

        # Not enough thresholds specified - work on case-by-case basis
        if len(channels[i]) > len(thresholds[i]):
            # Unsure which ones to match up - raise an error
            if len(channels[i]) > 1 and len(thresholds[i]) > 0:
                raise ValueError(f"Cannot determine which threshold from {thresholds[i]} should match which channel in {channels[i]}")
            
            # Either 1 channel and no threshold or multiple channels and no thresholds - fill with Nones
            else:
                thresholds[i] = [None]*len(channels[i])
        
        # Too many thresholds specified - raise an error
        elif len(channels[i]) < len(thresholds[i]):
            raise ValueError(f"Too many low pressure thresholds specified ({repr(thresholds[i])}) for channels {channels[i]}")
        
        # Same number of thresholds as channels - no problems!
        else:
            pass

        return thresholds

################################################################################
def create_gauges_from_command_line_arguments() -> list:
    """
    A function that converts command-line arguments into a list of VacuumGaugeBase objects

    Returns
    =======
    list_of_gauges : list[VacuumGaugeBase]
        A list of VacuumGaugeBase objects
    """
    parser = ap.ArgumentParser(prog='', description='', epilog='')
    parser.add_argument('-b', '--brand',                   help='brand of the vacuum gauge (\'pfeiffer\', \'edwards\', or \'mks\')',         metavar='BRAND',    default=None, dest='brand',        action='append' )
    parser.add_argument('-s', '--serial-number',           help='serial number of the vacuum gauge',                                         metavar='SN',       default=None, dest='serialnumber', action='append' )
    parser.add_argument('-c', '--channels',                help='list of channels to sample on the gauge',                                   metavar='CHAN',     default=None, dest='channel',      action='append' )
    parser.add_argument('-g', '--grafana-label',           help='name of the gauge in Grafana',                                              metavar='GRAFNAME', default=None, dest='grafana',      action='append' )
    parser.add_argument('-H', '--high-pressure-threshold', help='pressure (in mbar) above which to send an alert saying something is wrong', metavar='HP',       default=None, dest='hpthresh',     action='append' )
    parser.add_argument('-L', '--low-pressure-threshold',  help='pressure (in mbar) below which to send an alert saying everything is OK',   metavar='LP',       default=None, dest='lpthresh',     action='append' )
    parser.add_argument('-i', '--id',                      help='identifier for which instance of the script, in case something goes wrong', metavar='ID',       default=None, dest='id',           action='store')
    args = parser.parse_args()

    # Store arguments here
    serial_numbers = args.serialnumber
    brands = args.brand
    channels = args.channel
    grafana = args.grafana
    high_pressure_thresholds = args.hpthresh
    low_pressure_thresholds = args.lpthresh
    id = args.id

    # Check if nothing provided for thresholds and convert to list
    if low_pressure_thresholds == None:
        low_pressure_thresholds = [None]
    if high_pressure_thresholds == None:
        high_pressure_thresholds = [None]

    # Convert grafana names, channel names, and thresholds
    for i in range(len(channels)):
        channels[i] = _csv_str_to_list( channels[i], int )
        grafana[i] = _csv_str_to_list( grafana[i], str )
        low_pressure_thresholds[i] = _csv_str_to_list( low_pressure_thresholds[i], float )
        high_pressure_thresholds[i] = _csv_str_to_list( high_pressure_thresholds[i], float )

    # Possibility that no pressure thresholds specified. Ensure they are the same length with "None"
    low_pressure_thresholds = _create_optimal_thresholds_from_channels( channels, low_pressure_thresholds )
    high_pressure_thresholds = _create_optimal_thresholds_from_channels( channels, high_pressure_thresholds )

    # Check same number for each item
    if len(serial_numbers) != len(brands) or \
       len(serial_numbers) != len(brands) or \
       len(serial_numbers) != len(channels) or \
       len(serial_numbers) != len(grafana) or \
       len(serial_numbers) != len(low_pressure_thresholds) or \
       len(serial_numbers) != len(high_pressure_thresholds):
        print(f"Serial numbers:           {len(serial_numbers)}")
        print(f"Brands:                   {len(brands)}")
        print(f"Channels:                 {len(channels)}")
        print(f"Grafana name:             {len(grafana)}")
        print(f"High-pressure thresholds: {len(high_pressure_thresholds)}")
        print(f"Low-pressure thresholds:  {len(low_pressure_thresholds)}")
        print("Must be same number of every item to initialise gauges correctly. ERROR!")
        return None
    
    # Check same length for channels, grafana names - pressure thresholds already checked!
    for i in range(0,len(channels)):
        if len(channels[i]) != len(grafana[i]):
            raise IndexError(f"Mismatch between number of channels = {channels[i]} and list of grafana names = {grafana[i]}")
        
    # Check brand names
    for i in range(0,len(brands)):
        while type( brands[i] ) == list:
            if len(brands[i]) > 1:
                raise IndexError(f"Cannot parse object with length > 1: {brands}")
            brands[i] = brands[i][0]
        
        brands[i] = gauges.GaugeBrand.get_brand_from_str( brands[i] )

    # Turn gauge numbers into a list of numbers
    list_of_gauges = []
    for i in range(0,len(serial_numbers)):
        list_of_gauges.append( gauges.VacuumGauge( brands[i], serial_numbers[i], channels[i], grafana[i] ) )

    # Sanitise ID input
    if id == None:
        id = '[someone forgot to identify the script - more work for you!]'

    return list_of_gauges, id

################################################################################
def init_mattermost_interface( filepath : str ) -> mp.MattermostInterface:
    """
    Creates the Mattermost interface for posting messages, and supplies default
    arguments for each message

    Parameters
    ==========
    filepath : str
        The file path for the incoming webhook URL. Can also be the URL itself...
    
    Returns
    =======
    interface : mattermostpython.MattermostInterface
        The interface for posting messages to Mattermost
    """
    interface = mp.MattermostInterface( filepath )
    if interface == None:
        print("Couldn't establish mattermost connection")
        return None
    
    # Set default message properties here
    mp.MattermostMessage.set_default_username( 'pi@issmonitorpi read_vacuum.py' )
    mp.MattermostMessage.set_default_icon_url( 'https://twiki.cern.ch/twiki/pub/ISS/MattermostIcons/Raspberry_Pi_Logo.svg')
    mp.MattermostMessage.set_default_footer( 'Message delivered by the ISS Raspberry Pi' )
    mp.MattermostMessage.set_default_notification_message( 'Vacuum pressure alert!' )
    return interface