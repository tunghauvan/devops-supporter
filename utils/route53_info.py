import boto3
import csv
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_route53_records(output_csv_file='route53_records.csv'):
    """
    Fetches all Route 53 hosted zones and their record sets, saving them to a CSV file.

    Args:
        output_csv_file (str): The path to the output CSV file.
    """
    route53_client = boto3.client('route53')
    all_records_data = []
    headers = ['ZoneId', 'ZoneName', 'RecordName', 'RecordType', 'TTL', 'Value', 'AliasTargetDNSName', 'AliasTargetHostedZoneId', 'AliasTargetEvaluateTargetHealth']

    try:
        logging.info("Fetching hosted zones...")
        hosted_zones_paginator = route53_client.get_paginator('list_hosted_zones')
        hosted_zones_pages = hosted_zones_paginator.paginate()

        for page in hosted_zones_pages:
            for zone in page.get('HostedZones', []):
                zone_id = zone['Id'].split('/')[-1] # Extract ID like Z0123456789ABCDEFGHIJ
                zone_name = zone['Name']
                logging.info(f"Processing zone: {zone_name} ({zone_id})")

                try:
                    record_sets_paginator = route53_client.get_paginator('list_resource_record_sets')
                    record_sets_pages = record_sets_paginator.paginate(HostedZoneId=zone_id)

                    for record_page in record_sets_pages:
                        for record in record_page.get('ResourceRecordSets', []):
                            record_name = record['Name']
                            record_type = record['Type']
                            ttl = record.get('TTL', '') # TTL might not exist for Alias records
                            values = []
                            alias_target_dns_name = ''
                            alias_target_hosted_zone_id = ''
                            alias_target_evaluate_health = ''

                            if 'ResourceRecords' in record:
                                values = [rr['Value'] for rr in record['ResourceRecords']]
                            elif 'AliasTarget' in record:
                                alias_target = record['AliasTarget']
                                alias_target_dns_name = alias_target.get('DNSName', '')
                                alias_target_hosted_zone_id = alias_target.get('HostedZoneId', '')
                                alias_target_evaluate_health = alias_target.get('EvaluateTargetHealth', '')

                            # Handle multiple values by creating separate rows or joining them
                            # Here, we join them with a newline character for simplicity in CSV
                            value_str = "\n".join(values)

                            all_records_data.append({
                                'ZoneId': zone_id,
                                'ZoneName': zone_name,
                                'RecordName': record_name,
                                'RecordType': record_type,
                                'TTL': ttl,
                                'Value': value_str,
                                'AliasTargetDNSName': alias_target_dns_name,
                                'AliasTargetHostedZoneId': alias_target_hosted_zone_id,
                                'AliasTargetEvaluateTargetHealth': alias_target_evaluate_health
                            })

                except Exception as e:
                    logging.error(f"Error fetching records for zone {zone_name} ({zone_id}): {e}")
                    continue # Continue to the next zone

        logging.info(f"Collected {len(all_records_data)} records in total.")

        # Write data to CSV
        logging.info(f"Writing data to {output_csv_file}...")
        with open(output_csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_records_data)

        logging.info(f"Successfully saved Route 53 records to {output_csv_file}")

    except Exception as e:
        logging.error(f"An error occurred during the process: {e}")

if __name__ == "__main__":
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Define the output file path relative to the script directory
    csv_output_path = os.path.join(script_dir, '.tmp.route53_all_records.csv')
    get_route53_records(csv_output_path)
