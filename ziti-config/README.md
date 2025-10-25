# Ziti Configuration Directory

This directory stores OpenZiti configuration files and enrollment tokens.

## Contents (after setup)

- `edge-device.jwt` - Enrollment token for the edge device identity
- `operator.jwt` - Enrollment token for the operator identity
- `edge-device.json` - Edge device identity configuration (after enrollment)
- `operator.json` - Operator identity configuration (after enrollment)

## Security Note

**Do not commit `.jwt` or `.json` files to git!** These contain secrets for authenticating to the OpenZiti network. They are already excluded in `.gitignore`.
