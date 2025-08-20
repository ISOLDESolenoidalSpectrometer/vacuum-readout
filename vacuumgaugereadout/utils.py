"""
Utils
=====

A list of handy functions for reading out information from the vacuum gauges
"""

import mattermostpython as mp

################################################################################
def csv_str_to_list( csv_str : str, cast_type = None  ) -> list:
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
def create_optimal_thresholds_from_channels( channels : list, thresholds : list ) -> list:
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

################################################################################
def count_numbers_in_list( mylist : list ) -> int:
    """
    Work out how many non-None items there are in a list

    Parameters
    ==========
    mylist : list
        List of items
    
    Returns
    =======
    answer : int
        Number of non-None items in the list
    """
    answer = 0
    if type(mylist) != list:
        return answer
    
    for i in range(0,len(mylist)):
        if type(mylist[i]) == list:
            answer += count_numbers_in_list(mylist[i])
        else:
            if mylist[i] != None:
                answer += 1
    return answer
