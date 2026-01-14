# Payment Service Runbook

## Overview
The Payment Service handles all transaction processing via Stripe and PayPal.

## Common Issues
### 1. Payment Failures
If payments are failing with "Connection Refused", check the upstream gateway status.

### 2. Service Restart Procedure
**To restart the payment service safely:**

1.  **Drain Connections**:
    ```bash
    curl -X POST localhost:8080/admin/drain
    ```
2.  **Wait** for active transactions to complete (approx 30s).
3.  **Restart Process**:
    ```bash
    systemctl restart payment-service
    ```
4.  **Verify Health**:
    ```bash
    curl localhost:8080/health
    ```

## Emergency Contacts
- --On-Call--: @payment-oncall
- **Manager**: Sarah Connor
