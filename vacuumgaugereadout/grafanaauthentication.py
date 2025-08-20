"""
Grafana Authenitcation
======================

This module deals with getting the username, password, and URL for sending data
to Grafana.
"""
################################################################################

def get_grafana_authentication(filepath : str) -> tuple:
    """
    Gets the authentication for sending data to Grafana. Note that the file should have the form:
    ```
    username -> xxxx
    password -> xxxx
    url -> xxxx
    ```

    Parameters
    ----------
    filepath : str
        The path to the text file containing the information.

    Returns
    -------
    details : tuple
        Three-element tuple of the form:
        ( username : str, password : str, url : str)
    """
    # Open the file and read each line
    try:
        with open(filepath, 'r') as file:
            # Check we capture all 3 needed items
            have_username = False
            have_password = False
            have_url = False

            # Loop over lines
            for line in file:
                line = line.strip()
                if line.count('->') != 1:
                    continue
                
                # Split at -> delimeter
                split = line.split('->')
                key = split[0].strip()
                value = split[1].strip()

                # Store authentication details
                if key == 'username':
                    if have_username == True:
                        print('Ignoring duplicate username...')
                        continue
                    grafana_username = value
                    have_username = True

                elif key == 'password':
                    if have_password == True:
                        print('Ignoring duplicate password...')
                        continue
                    grafana_password = value
                    have_password = True

                elif key == 'url':
                    if have_url == True:
                        print('Ignoring duplicate url...')
                        continue
                    grafana_url = value
                    have_url = True
                else:
                    print(f'Could not parse line \"{line}\"')

            # Check we have all 3 options after the end of the file
            if have_username and have_password and have_url:
                return ( grafana_username, grafana_password, grafana_url )
            else:
                raise ValueError(f'Cannot parse grafana details: USER = {grafana_username}, PASSWORD = {grafana_password}, URL = {grafana_url}')
            
    except FileNotFoundError:
        raise FileNotFoundError("FileNotFoundError: Could not get the file for Grafana.")
    
    return None