# Bellhop Trolley

This package contains 

## Configuration

```python
import bellhop_trolley

# Permanent — sets global state for the rest of the process
bellhop_trolley.configure(local=LocalTransferSettings(copy_method="robocopy"))
bellhop_trolley.transfer_data(src, dst)

# Temporary — restores previous settings on exit
with bellhop_trolley.configure(s3=S3TransferSettings(multipart_threshold=10_000)):
    bellhop_trolley.transfer_data(src, dst)
```

## Authentication for cloud storage

## AWS
IAM RolesAnywhere is the proper way to authenticate from a non-AWS computer. It requires downloading the [aws_signing_helper tool](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html), and setting up a `~/.aws/config` file that looks something like this:

```toml
[profile default]
credential_process = C:/Program Files/Amazon/aws_signing_helper.exe credential-process --certificate path/to/certificate.pem --private-key path/to/private_key_unencrypted.pem --trust-anchor-arn arn:aws:rolesanywhere:us-east-1:123456789012:trust-anchor/xxx --profile-arn arn:aws:rolesanywhere:us-east-1:123456789012:profile/yyy --role-arn arn:aws:iam::123456789012:role/MyExternalWorkloadRole
```

You'll need to receive certificate.pem, private_key_unencrypted.pem, and trust-anchor, profile, and role ARNs from your AWS administrator.

### Google Cloud
To interact with the google cloud file system, download the google cloud CLI: https://cloud.google.com/sdk/docs/install.

Once set up, authenticate using a service account with 

`gcloud auth activate-service-account --key-file=/path/to/your/service-account.json`

List files in a bucket with:

`gsutil ls gs://your-bucket-name/`