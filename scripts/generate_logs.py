import os
import random
import json
import argparse
from datetime import datetime, timedelta

def generate_logs(output_dir: str = "data/source/landing_zone", count: int = 1000, log_format: str = "standard"):
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

    print(f"Generating {count} logs into {output_dir} (Format: {log_format})...")

    # Prepare file handles
    files = {name: open(os.path.join(output_dir, filename), "w") for name, filename in services.items()}

    try:
        for i in range(count):
            timestamp = start_time + timedelta(minutes=i*5)
            
            service_name = random.choice(list(services.keys()))
            severity = random.choice(severities)
            
            # Generate message
            # Add standard metadata
            env = "prod"
            region = random.choice(["us-east-1", "us-west-2", "eu-central-1"])
            host = f"server-{random.randint(1, 100):03d}"
            
            meta = f"env={env} region={region} host={host}"
            msg_body = ""
            context = {}

            if service_name == "payment-service":
                uid = random.randint(100, 200)
                amt = random.randint(10, 500)
                dept = "finance"
                app_id = "com.example.payment"
                msg_body = f"Payment processed for user_id={uid} amount={amt}.00"
                context = {"user_id": uid, "amount": amt, "dept": dept, "app_id": app_id}
            elif service_name == "auth-service":
                user = random.choice(["admin", "guest", "user1", "user2"])
                ip = f"192.168.1.{random.randint(1, 255)}"
                dept = "security"
                app_id = "com.example.auth"
                success = random.random() > 0.2
                msg_body = f"Login success for user={user} ip={ip}" if success else f"Login failed for user={user} ip={ip} reason=bad_password"
                context = {"user": user, "ip": ip, "reason": "bad_password" if not success else None, "dept": dept, "app_id": app_id}
            elif service_name == "db-service":
                table = random.choice(["users", "orders", "products"])
                dur = random.randint(10, 1000)
                dept = "infra"
                app_id = "com.example.db"
                msg_body = f"Query executed on table={table} duration={dur}ms"
                context = {"table": table, "duration": dur, "dept": dept, "app_id": app_id}
            else:
                dept = "product"
                app_id = "com.example.frontend"
                msg_body = f"Page view /home"
                context = {"path": "/home", "dept": dept, "app_id": app_id}

            # Format the log line
            log_line = ""
            
            if log_format == "json":
                log_entry = {
                    "timestamp": timestamp.isoformat() + "Z",
                    "level": severity,
                    "service": service_name,
                    "message": msg_body,
                    "host": host,
                    "region": region,
                    **context
                }
                log_line = json.dumps(log_entry) + "\n"
                
            elif log_format == "syslog":
                # Nov 24 16:00:00 host service[123]: message
                ts_str = timestamp.strftime("%b %d %H:%M:%S")
                log_line = f"{ts_str} {host} {service_name}[{random.randint(100,999)}]: {msg_body} {meta}\n"
                
            elif log_format == "nginx":
                # IP - - [Date] "Request" Status Bytes
                # Only really makes sense for frontend, but we'll force fit others
                ip = context.get("ip", "127.0.0.1")
                ts_str = timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")
                req = f"GET {context.get('path', '/api')} HTTP/1.1"
                status = 200 if severity == "INFO" else 500
                bytes_sent = random.randint(100, 5000)
                log_line = f'{ip} - - [{ts_str}] "{req}" {status} {bytes_sent}\n'
                
            else: # Standard
                timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                # Append meta to body for standard format to keep context
                full_msg = f"{msg_body} {meta} " + " ".join([f"{k}={v}" for k,v in context.items() if v])
                log_line = f"{timestamp_str} {severity} {service_name}: {full_msg}\n"

            files[service_name].write(log_line)

    finally:
        for f in files.values():
            f.close()
    
    print("✅ Log generation complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate mock logs.")
    parser.add_argument("--count", type=int, default=1000, help="Number of logs to generate.")
    parser.add_argument("--output_dir", type=str, default="data/source/landing_zone", help="Output directory.")
    parser.add_argument("--format", type=str, default="standard", choices=["standard", "json", "syslog", "nginx"], help="Log format.")
    
    args = parser.parse_args()
    generate_logs(output_dir=args.output_dir, count=args.count, log_format=args.format)
