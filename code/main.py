from daytona import Daytona, DaytonaConfig
  
# Define the configuration
config = DaytonaConfig(api_key="dtn_365e51be704c3547c70b412f156657030e19cdc05bbaac80d4a76344bf90cfbb")

# Initialize the Daytona client
daytona = Daytona(config)

# Create the Sandbox instance
sandbox = daytona.create()

# Run the code securely inside the Sandbox
response = sandbox.process.code_run('print("Hello World from code!")')
if response.exit_code != 0:
  print(f"Error: {response.exit_code} {response.result}")
else:
    print(response.result)