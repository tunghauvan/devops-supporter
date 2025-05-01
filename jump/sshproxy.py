import boto3
import logging
import csv
import os
import subprocess
# Add prompt_toolkit imports
from prompt_toolkit import prompt
from prompt_toolkit.completion import FuzzyCompleter
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory # Optional: for command history

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_running_ec2_instances(region_name='us-east-1'):
    """
    Retrieves a list of running EC2 instances in the specified region,
    including a best-effort determination of the default SSH user based on AMI info.

    Args:
        region_name (str): The AWS region to query. Defaults to 'us-east-1'.

    Returns:
        list: A list of dictionaries, where each dictionary contains details
              of a running EC2 instance (InstanceId, Name, PrivateIpAddress, KeyName,
              TargetUser, PlatformDetails, ImageId, ImageName).
              Returns an empty list if an error occurs or no instances are found.
    """
    try:
        ec2_client = boto3.client('ec2', region_name=region_name)
        response = ec2_client.describe_instances(
            Filters=[
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )

        instances_list = []
        image_ids = set() # Use a set to store unique image IDs

        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                instance_id = instance.get('InstanceId')
                private_ip = instance.get('PrivateIpAddress')
                key_name = instance.get('KeyName', 'N/A')
                platform_details = instance.get('PlatformDetails', 'Linux/UNIX')
                image_id = instance.get('ImageId') # Get the ImageId

                # Initial guess for target user based on platform
                target_user = 'ec2-user' # Default for Amazon Linux, RHEL, CentOS, Fedora
                if 'ubuntu' in platform_details.lower():
                    target_user = 'ubuntu'
                elif 'windows' in platform_details.lower():
                     target_user = 'Administrator'

                instance_name = 'N/A'
                for tag in instance.get('Tags', []):
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break

                instance_data = {
                    'InstanceId': instance_id,
                    'Name': instance_name,
                    'PrivateIpAddress': private_ip,
                    'KeyName': key_name,
                    'TargetUser': target_user, # Initial guess
                    'PlatformDetails': platform_details,
                    'ImageId': image_id or 'N/A', # Store N/A if None
                    'ImageName': 'N/A' # Placeholder for AMI Name
                }
                instances_list.append(instance_data)
                if image_id:
                    image_ids.add(image_id)

        # --- Refine TargetUser based on AMI details ---
        if image_ids:
            try:
                logging.info(f"Describing {len(image_ids)} unique AMIs...")
                images_response = ec2_client.describe_images(ImageIds=list(image_ids))
                ami_info_map = {img['ImageId']: {'Name': img.get('Name', ''), 'Description': img.get('Description', '')}
                                for img in images_response.get('Images', [])}

                for instance in instances_list:
                    img_id = instance['ImageId']
                    if img_id in ami_info_map:
                        ami_name = ami_info_map[img_id].get('Name', '').lower()
                        ami_desc = ami_info_map[img_id].get('Description', '').lower()
                        instance['ImageName'] = ami_info_map[img_id].get('Name', 'N/A') # Store actual AMI name

                        # Refine user based on AMI name/description keywords
                        if 'ubuntu' in ami_name or 'ubuntu' in ami_desc:
                            instance['TargetUser'] = 'ubuntu'
                        elif 'centos' in ami_name or 'centos' in ami_desc:
                             instance['TargetUser'] = 'centos'
                        elif 'rhel' in ami_name or 'rhel' in ami_desc:
                             instance['TargetUser'] = 'ec2-user' # RHEL often uses ec2-user
                        elif 'fedora' in ami_name or 'fedora' in ami_desc:
                             instance['TargetUser'] = 'fedora'
                        elif 'amzn2' in ami_name or 'amazon linux 2' in ami_desc:
                             instance['TargetUser'] = 'ec2-user' # Amazon Linux 2 uses ec2-user
                        elif 'amazon linux ami' in ami_name or 'amzn-ami' in ami_name:
                             instance['TargetUser'] = 'ec2-user' # Original Amazon Linux uses ec2-user
                        # Add more rules as needed (e.g., Debian, SUSE)

            except Exception as e:
                logging.warning(f"Could not describe AMIs to refine user: {e}")
                # Proceed with the initial guesses if AMI description fails

        logging.info(f"Found {len(instances_list)} running instances in {region_name}.")
        return instances_list
    except Exception as e:
        logging.error(f"Error fetching running EC2 instances in {region_name}: {e}")
        return []

# Modify ssh_via_jump_host for nested SSH command
def ssh_via_jump_host(target_ip, target_user, jump_host_ip, jump_host_user, local_jump_key_path, remote_target_key_path):
    """
    Initiates an SSH connection to a target instance via a jump host using nested SSH,
    specifying keys for both connections.

    Args:
        target_ip (str): The private IP address of the target instance.
        target_user (str): The username for the target instance (e.g., 'ec2-user', 'ubuntu').
        jump_host_ip (str): The public IP address or DNS name of the jump host.
        jump_host_user (str): The username for the jump host (e.g., 'ec2-user').
        local_jump_key_path (str): Path to the private key *on the local machine* for jump host access.
        remote_target_key_path (str): Path to the private key *on the jump host* for target instance access.

    Returns:
        None: This function attempts to launch an interactive SSH session.
    """
    if not all([target_ip, target_user, jump_host_ip, jump_host_user, local_jump_key_path, remote_target_key_path]):
        logging.error("Missing required SSH parameters for nested SSH.")
        print("Error: Missing required SSH parameters (target IP/user, jump host IP/user, local key, remote key).")
        return

    # Expand user path for local key
    local_jump_key_path = os.path.expanduser(local_jump_key_path)
    if not os.path.exists(local_jump_key_path):
        logging.error(f"Local jump key file not found: {local_jump_key_path}")
        print(f"Error: Local jump key file not found: {local_jump_key_path}")
        return

    # Construct the nested SSH command
    jump_string = f"{jump_host_user}@{jump_host_ip}"
    # Command to be executed on the jump host
    remote_command = f"ssh -i {remote_target_key_path} {target_user}@{target_ip}"

    ssh_command = [
        'ssh',
        '-i', local_jump_key_path,
        '-t', # Allocate pseudo-terminal
        jump_string,
        remote_command # The command to run on the jump host
    ]

    logging.info(f"Attempting nested SSH connection: {' '.join(ssh_command)}")
    print(f"\nAttempting nested SSH:")
    print(f"  Local -> Jump: ssh -i '{local_jump_key_path}' -t {jump_string}")
    print(f"  Jump -> Target: ssh -i '{remote_target_key_path}' {target_user}@{target_ip}")
    print(f"\nExecuting Command: {' '.join(ssh_command)}")

    try:
        result = subprocess.run(ssh_command)
        if result.returncode == 0:
            print("SSH session ended.")
        else:
            print(f"SSH command failed with return code {result.returncode}.")
            logging.warning(f"SSH command failed with return code {result.returncode}.")

    except FileNotFoundError:
        logging.error("SSH command not found. Make sure OpenSSH client is installed and in your PATH.")
        print("Error: 'ssh' command not found. Is OpenSSH client installed and in your PATH?")
    except Exception as e:
        logging.error(f"Failed to execute SSH command: {e}")
        print(f"An error occurred while trying to execute SSH: {e}")

# Example usage (optional - can be removed or placed under __main__)
if __name__ == '__main__':
    # Define the output file path relative to the script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_filename = os.path.join(script_dir, '.tmp.csv')
    history_filename = os.path.join(script_dir, '.sshproxy_history') # For command history
    target_region = 'ap-southeast-1' # Example region

    # Function to load or fetch instances (extracted for re-use)
    def load_or_fetch_instances(force_fetch=False):
        running_instances = []
        fetch_from_aws = force_fetch

        if not force_fetch and os.path.exists(csv_filename):
            print(f"Cache file found: {csv_filename}. Loading data from cache.")
            try:
                # ... (existing cache loading logic) ...
                with open(csv_filename, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    if not reader.fieldnames:
                         print("Cache file is empty or invalid. Fetching from AWS.")
                         running_instances = None
                    else:
                        running_instances = list(reader)
                        if not running_instances:
                            print("Cache file contains no instance data. Fetching from AWS.")
                        else:
                             logging.info(f"Loaded {len(running_instances)} instances from {csv_filename}")

            except (IOError, csv.Error, Exception) as e:
                logging.error(f"Error reading or parsing cache file {csv_filename}: {e}")
                print(f"Error reading cache file {csv_filename}. Fetching from AWS.")
                running_instances = None

            if running_instances is None or not running_instances:
                 fetch_from_aws = True
            else:
                 fetch_from_aws = False
        elif not force_fetch:
            print(f"Cache file not found: {csv_filename}. Fetching data from AWS.")
            fetch_from_aws = True
        else:
             print("Forcing refresh from AWS...")
             fetch_from_aws = True


        if fetch_from_aws:
            running_instances = get_running_ec2_instances(region_name=target_region)
            if running_instances:
                print(f"Fetched {len(running_instances)} running instances from AWS ({target_region}).")
                # ... (existing cache writing logic) ...
                header = running_instances[0].keys()
                try:
                    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=header)
                        writer.writeheader()
                        writer.writerows(running_instances)
                    print(f"Instance data saved to cache file: {csv_filename}")
                except IOError as e:
                    logging.error(f"Error writing to CSV file {csv_filename}: {e}")
                    print(f"Error: Could not write instance data to {csv_filename}")
            else:
                print(f"No running instances found in {target_region} or an error occurred during fetch.")
                # ... (existing cache removal logic) ...
                if os.path.exists(csv_filename):
                    try:
                        os.remove(csv_filename)
                        print(f"Removed potentially outdated cache file: {csv_filename}")
                    except OSError as e:
                        logging.error(f"Error removing file {csv_filename}: {e}")

        return running_instances

    # Function to display instances
    def display_instances(instances):
        if not instances:
            print("No running instance data available.")
            return
        print("\nRunning EC2 Instances:")
        for i, instance in enumerate(instances):
             instance_id = instance.get('InstanceId', 'N/A')
             instance_name = instance.get('Name', 'N/A')
             private_ip = instance.get('PrivateIpAddress', 'N/A')
             key_name = instance.get('KeyName', 'N/A')
             target_user_display = instance.get('TargetUser', 'N/A')
             image_name_display = instance.get('ImageName', 'N/A')
             # Simplified display for prompt list
             print(f"  [{i+1}] {instance_name} ({instance_id}) - IP: {private_ip}, User: {target_user_display}, Key: {key_name}, AMI: {image_name_display}")


    # --- Main Loop ---
    running_instances = load_or_fetch_instances()
    session_history = FileHistory(history_filename)

    while True:
        instance_choices = []
        instance_map = {} # Map choice string back to instance data
        if running_instances:
            for i, inst in enumerate(running_instances):
                choice_str = f"[{i+1}] {inst.get('Name', 'N/A')} ({inst.get('InstanceId', 'N/A')})"
                instance_choices.append(choice_str)
                instance_map[choice_str] = inst

        # Add commands to completer
        command_suggestions = ['exit', 'quit', 'refresh', 'list']
        all_suggestions = command_suggestions + instance_choices
        completer = FuzzyCompleter(WordCompleter(all_suggestions, ignore_case=True))

        try:
            user_input = prompt(
                'Select instance or command (exit, refresh, list): ',
                completer=completer,
                history=session_history,
                complete_while_typing=True
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ['exit', 'quit']:
                break
            elif user_input.lower() == 'refresh':
                running_instances = load_or_fetch_instances(force_fetch=True)
                continue # Reload choices in the next loop iteration
            elif user_input.lower() == 'list':
                display_instances(running_instances)
                continue

            # Check if input matches an instance choice
            selected_instance = instance_map.get(user_input)

            if selected_instance:
                target_ip = selected_instance.get('PrivateIpAddress')
                raw_key_name = selected_instance.get('KeyName', '')
                target_user = selected_instance.get('TargetUser')

                key_name_base = raw_key_name.split('_')[0] if raw_key_name and raw_key_name != 'N/A' else None
                remote_target_key_path = f"/home/ec2-user/keys/{key_name_base}.pem" if key_name_base else None

                if not target_ip:
                    print("Error: Selected instance does not have a Private IP address.")
                elif not target_user:
                     print("Error: Could not determine target user for the selected instance.")
                elif not remote_target_key_path:
                    print(f"Warning: Could not determine remote key file path on jump host from KeyName '{raw_key_name}'. Cannot proceed with nested SSH.")
                else:
                    # Proceed if target_ip, target_user, and remote_target_key_path are available
                    jump_host_ip = "172.31.12.76" # Replace with your jump host IP/DNS
                    jump_host_user = "ec2-user"   # Replace with your jump host user
                    local_jump_key_path = "~/.ssh/id_ed25519" # Example: Replace with your actual local key path

                    print(f"\nSelected: {selected_instance.get('Name')} ({target_ip})")
                    print(f"Target User: {target_user} (determined from AMI info/defaults)")
                    print(f"Using local key '{local_jump_key_path}' to connect to jump host {jump_host_user}@{jump_host_ip}.")
                    print(f"Using remote key '{remote_target_key_path}' on jump host to connect to target {target_user}@{target_ip}.")

                    # Remove confirmation prompt
                    # confirm = input("Proceed with nested SSH connection? (y/n): ")
                    # if confirm.lower() == 'y':
                    ssh_via_jump_host(
                        target_ip=target_ip,
                        target_user=target_user,
                        jump_host_ip=jump_host_ip,
                        jump_host_user=jump_host_user,
                        local_jump_key_path=local_jump_key_path,
                        remote_target_key_path=remote_target_key_path
                    )
                    # Optional: break after successful connection attempt or stay in loop
                    # else:
                    #    print("SSH connection cancelled.")
            else:
                print(f"Unknown command or instance: '{user_input}'. Use Tab for suggestions.")

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\nOperation cancelled by user (Ctrl+C). Type 'exit' or 'quit' to leave.")
            continue # Go to next prompt iteration
        except EOFError:
            # Handle Ctrl+D
            break # Exit the loop

    print('Goodbye!')
