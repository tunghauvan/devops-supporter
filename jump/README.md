# EC2 SSH Proxy via Jump Host

This Python script facilitates SSH connections to private EC2 instances within an AWS VPC by routing the connection through a designated jump host (bastion). It fetches running instances, attempts to determine the appropriate SSH user based on AMI information, and provides an interactive prompt for selecting the target instance.

## Features

*   Fetches running EC2 instances from a specified AWS region.
*   Automatically attempts to determine the default SSH user (`ec2-user`, `ubuntu`, `centos`, etc.) based on platform details and AMI name/description.
*   Uses an interactive prompt with fuzzy completion (`prompt_toolkit`) to select the target instance.
*   Connects via a specified jump host using nested SSH (`ssh -t jump_host 'ssh target_host'`).
*   Requires the private key for the *jump host* to be available locally and managed by `ssh-agent` or specified directly.
*   Requires the private keys for the *target instances* to be present on the *jump host* in a predefined location (e.g., `/home/ec2-user/keys/`).
*   Caches instance information locally (`.tmp.csv`) to speed up subsequent runs.
*   Supports refreshing the instance list (`refresh` command).
*   Supports listing the cached/fetched instances (`list` command).

## Prerequisites

1.  **Python 3:** Ensure Python 3 is installed.
2.  **Pip:** Python package installer.
3.  **AWS Account & Credentials:** Configured AWS credentials with permissions to `ec2:DescribeInstances` and `ec2:DescribeImages`. The script uses `boto3`, which looks for credentials in the standard locations (environment variables, `~/.aws/credentials`, IAM role).
4.  **Boto3 & Prompt Toolkit:** Python libraries.
5.  **OpenSSH Client:** The `ssh` command must be available in your system's PATH.
6.  **SSH Agent:** `ssh-agent` should be running to manage the private key for accessing the *jump host*.
7.  **Jump Host:** An EC2 instance or other server configured as a jump host, accessible from your local machine.
8.  **Target Instance Keys on Jump Host:** The private keys corresponding to the `KeyName` associated with your target EC2 instances must exist on the jump host (see Setup).

## Setup

1.  **Clone or Download:** Place the `sshproxy.py` script in your desired directory.
2.  **Install Dependencies:**
    ```bash
    pip install boto3 prompt_toolkit
    ```
3.  **Configure AWS Credentials:** Ensure your AWS credentials are set up correctly for `boto3`. Refer to the [Boto3 Credentials Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).
4.  **Setup SSH Agent (Local Machine):**
    The script uses your local SSH key to connect to the *jump host*. Add the private key used to access the **jump host** to your `ssh-agent`.

    *   **Check if agent is running:**
        ```bash
        eval "$(ssh-agent -s)"
        # or for fish shell: eval (ssh-agent -c)
        ```
        *(This command will start the agent if it's not running and set the necessary environment variables).*

    *   **Add your jump host private key:** Replace `~/.ssh/your_jump_host_key` with the actual path to your key.
        ```bash
        ssh-add ~/.ssh/your_jump_host_key
        ```
        *(You might be prompted for the key's passphrase if it has one).*

    *   **Verify the key is added:**
        ```bash
        ssh-add -l
        ```

5.  **Prepare Jump Host:**
    *   Ensure the jump host is running and accessible via SSH from your local machine using the key added to `ssh-agent`.
    *   Place the private keys (`.pem` files) for your **target EC2 instances** onto the jump host. The script assumes these keys are located in a specific directory on the jump host (e.g., `/home/ec2-user/keys/`). It constructs the path like `/home/<jump_host_user>/keys/<key_name_base>.pem`, where `<key_name_base>` is derived from the `KeyName` tag of the target instance (e.g., if `KeyName` is `my-app-key_us-east-1`, it looks for `my-app-key.pem`). Adjust the `remote_target_key_path` logic in the script if your setup differs.
    *   Ensure the permissions on the keys on the jump host are appropriate (e.g., `chmod 400 /home/ec2-user/keys/*.pem`).

6.  **Configure Script Variables:**
    Open `sshproxy.py` and modify the variables within the `if __name__ == '__main__':` block:
    *   `target_region`: Set your desired AWS region (e.g., `'us-east-1'`, `'ap-southeast-1'`).
    *   `jump_host_ip`: Set the public IP address or DNS name of your jump host.
    *   `jump_host_user`: Set the SSH username for your jump host (e.g., `'ec2-user'`).
    *   `local_jump_key_path`: **Important:** While `ssh-agent` is recommended, the script currently includes a `-i local_jump_key_path` argument in the `ssh` command. If you are *only* using `ssh-agent`, you might want to remove the `-i` flag and `local_jump_key_path` from the `ssh_command` list within the `ssh_via_jump_host` function for cleaner agent usage. If you prefer specifying the key directly (and not using the agent), ensure this path points to the correct local private key for the jump host.
    *   *(Optional)* Modify the logic for `remote_target_key_path` if your keys are stored differently on the jump host.

## Usage

1.  **Run the script:**
    ```bash
    python sshproxy.py
    ```
2.  **First Run:** The script will fetch running EC2 instances from the specified AWS region and save them to `.tmp.csv`.
3.  **Subsequent Runs:** The script will load instances from the cache file unless you use the `refresh` command.
4.  **Interactive Prompt:**
    *   Start typing the instance name or ID. Use `Tab` for autocompletion.
    *   Select the desired instance from the list (e.g., `[1] MyInstance (i-0123...)`) and press `Enter`.
    *   The script will construct and execute the nested SSH command.
5.  **Commands:**
    *   `list`: Display the currently loaded list of instances.
    *   `refresh`: Clear the local cache and fetch the latest instance list from AWS.
    *   `exit` or `quit`: Exit the script.
    *   `Ctrl+C`: Cancel the current prompt.
    *   `Ctrl+D`: Exit the script (EOF).

## Caching

Instance data is cached in `.tmp.csv` in the same directory as the script. Use the `refresh` command to update this cache. If the cache file is invalid or fetching fails, the script will attempt to proceed without cached data or remove the invalid cache.

## Troubleshooting

*   **Permissions Error (AWS):** Ensure your AWS credentials have the necessary `ec2:DescribeInstances` and `ec2:DescribeImages` permissions.
*   **SSH Connection Refused/Timeout (Jump Host):** Verify the jump host IP/DNS is correct, the jump host is running, security groups/firewalls allow SSH from your IP, and your local SSH key is correct (and added to `ssh-agent` if using it).
*   **SSH Permission Denied (Public Key) (Target Host):** Verify the correct private key for the target instance exists on the jump host at the expected path (e.g., `/home/ec2-user/keys/keyname.pem`), and its permissions are correct (`chmod 400`). Check that the `KeyName` tag on the EC2 instance matches the key file name (excluding region suffix if applicable).
*   **`ssh` command not found:** Ensure the OpenSSH client is installed and its location is in your system's PATH environment variable.
*   **`ssh-add: Could not open a connection to your authentication agent`:** Make sure `ssh-agent` is running (`eval "$(ssh-agent -s)"`).
*   **Incorrect Target User:** The script makes a best guess for the user based on AMI info. If it's wrong, you may need to adjust the logic in `get_running_ec2_instances` or manually specify the user if connecting manually.
