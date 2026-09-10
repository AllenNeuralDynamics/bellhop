from bellhop_trolley import transfer_data, delete_data


transfer_data("local/source/path", "local/destination/path")

# Upload to AWS (automatically detects based on destination url prefix)
transfer_data("local/source/path", "s3://bucket/key")

# Upload to Google Cloud Storage (automatically detects based on destination url prefix)
transfer_data("local/source/path", "gs://bucket/key")

# Download from AWS (automatically detects based on source url prefix)
transfer_data("s3://bucket/key", "local/destination/path")

# Delete data
delete_data("local/destination/path")
