from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

config = TemplateMinerConfig()
miner = TemplateMiner(None, config)

log_line1 = "User bob failed to login in 5 seconds"
log_line2 = "User alice failed to login in 10 seconds"

print("--- Run 1 ---")
result1 = miner.add_log_message(log_line1)
print(f"Template: {result1['template_mined']}")

print("--- Run 2 ---")
result2 = miner.add_log_message(log_line2)
print(f"Template: {result2['template_mined']}")

# Check if we can get parameters
cluster = miner.match(log_line2)
if cluster:
    print(f"Matched Cluster ID: {cluster.cluster_id}")
    print(f"Cluster Template: {cluster.get_template()}")
    
    # Extract parameters
    template = cluster.get_template()
    # Simple extraction logic (Drain3 might have this internally but let's see)
    # The template has <*>. We can use regex to extract.
    import re
    regex = re.escape(template).replace(re.escape("<*>"), "(.*?)")
    match = re.match(regex, log_line2)
    if match:
        print(f"Extracted Parameters: {match.groups()}")
    else:
        print("Failed to extract parameters with regex")
else:
    print("No match found")
