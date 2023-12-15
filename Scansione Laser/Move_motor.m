% Initialize Kinesis API
NET.addAssembly('Thorlabs.MotionControl.DeviceManagerCLI');
NET.addAssembly('Thorlabs.MotionControl.GenericMotorCLI');
NET.addAssembly('Thorlabs.MotionControl.KCube.StepperMotorCLI');

% Connect to the device
serialNumber = 83815649; % Replace with your actual serial number
deviceIndex = 0; % Replace with your actual device index
kinesisWrapper = Thorlabs.MotionControl.DeviceManagerCLI.DeviceManagerCLI.GetDeviceManagerCLI();
device = kinesisWrapper.OpenDevice(serialNumber, deviceIndex);

% Set motor parameters
motor = Thorlabs.MotionControl.KCube.StepperMotorCLI.KST101;
motor.SetDevice(device);

% Home the motor
motor.Home();

% Wait for homing to complete
while motor.IsHoming
    pause(0.1);
end

disp('Homing completed.');

% Set move parameters
moveDistance_mm = 1; % Move 1 mm
stepsPerRevolution = 200; % Replace with the actual steps per revolution of your motor
stepsToMove = round(stepsPerRevolution * moveDistance_mm);

% Move the motor
motor.MoveTo(stepsToMove);

% Wait for the movement to complete
while motor.IsMoving
    pause(0.1);
end

disp('Movement completed.');

% Clean up
motor.ClearDevice();
device.ClearDevice();