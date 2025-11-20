import os
import random
from datetime import datetime, timedelta

def generate_logs(output_dir: str = "data/landing_zone", count: int = 1000):
    """Generates sample log files simulating different services."""
    os.makedirs(output_dir, exist_ok=True)
    
    services = {
        "payment-service": "payment.log",
        "auth-service": "auth.log",
        "db-service": "database.log",
        "frontend": "access.log"
    }
    
    severities = ["INFO", "WARN", "ERROR"]
    start_time = datetime.now() - timedelta(days=30)

    print(f"Generating {count} logs into {output_dir}...")

    # Prepare file handles
    files = {name: open(os.path.join(output_dir, filename), "w") for name, filename in services.items()}

    try:
        for i in range(count):
            timestamp = start_time + timedelta(minutes=i*5)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            service_name = random.choice(list(services.keys()))
            severity = random.choice(severities)
            
            # Generate message
            # Add standard metadata
            env = "prod"
            region = random.choice(["us-east-1", "us-west-2", "eu-central-1"])
            host = f"server-{random.randint(1, 100):03d}"
            
            meta = f"env={env} region={region} host={host}"

            if service_name == "payment-service":
                uid = random.randint(100, 200)
                amt = random.randint(10, 500)
                dept = "finance"
                app_id = "com.example.payment"
                msg = f"Payment processed for user_id={uid} amount={amt}.00 {meta} dept={dept} app_id={app_id}"
            elif service_name == "auth-service":
                user = random.choice(["admin", "guest", "user1", "user2"])
                ip = f"192.168.1.{random.randint(1, 255)}"
                dept = "security"
                app_id = "com.example.auth"
                msg = f"Login success for user={user} ip={ip} {meta} dept={dept} app_id={app_id}" if random.random() > 0.2 else f"Login failed for user={user} ip={ip} reason=bad_password {meta} dept={dept} app_id={app_id}"
            elif service_name == "db-service":
                table = random.choice(["users", "orders", "products"])
                dur = random.randint(10, 1000)
                dept = "infra"
                app_id = "com.example.db"
                msg = f"Query executed on table={table} duration={dur}ms {meta} dept={dept} app_id={app_id}"
            else:
                dept = "product"
                app_id = "com.example.frontend"
                msg = f"Page view /home {meta} dept={dept} app_id={app_id}"

            # Write to specific file
            # Format: TIMESTAMP SEVERITY SERVICE: MESSAGE
            log_line = f"{timestamp_str} {severity} {service_name}: {msg}\n"
            files[service_name].write(log_line)

    finally:
        for f in files.values():
            f.close()
    
    print("✅ Log generation complete.")

if __name__ == "__main__":
    generate_logs()
