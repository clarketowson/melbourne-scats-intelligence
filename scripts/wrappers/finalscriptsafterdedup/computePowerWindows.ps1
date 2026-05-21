$OutFile = "$env:USERPROFILE\Desktop\windows10_compute_specs.txt"

"WINDOWS COMPUTE SPECS REPORT" | Out-File $OutFile
"Generated: $(Get-Date)" | Out-File $OutFile -Append
"=========================================" | Out-File $OutFile -Append

"`nCOMPUTER / OS" | Out-File $OutFile -Append
Get-ComputerInfo |
Select-Object CsName, WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture |
Format-List | Out-File $OutFile -Append

"`nCPU" | Out-File $OutFile -Append
Get-CimInstance Win32_Processor |
Select-Object Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed |
Format-List | Out-File $OutFile -Append

"`nMEMORY" | Out-File $OutFile -Append
Get-CimInstance Win32_PhysicalMemory |
Select-Object Manufacturer, Capacity, Speed, ConfiguredClockSpeed, DeviceLocator |
Format-Table -AutoSize | Out-File $OutFile -Append

"`nTOTAL RAM" | Out-File $OutFile -Append
Get-CimInstance Win32_ComputerSystem |
Select-Object @{Name="TotalPhysicalMemoryGB";Expression={[math]::Round($_.TotalPhysicalMemory/1GB,2)}} |
Format-List | Out-File $OutFile -Append

"`nGPU" | Out-File $OutFile -Append
Get-CimInstance Win32_VideoController |
Select-Object Name, AdapterRAM, DriverVersion, VideoProcessor |
Format-List | Out-File $OutFile -Append

"`nDISKS" | Out-File $OutFile -Append
Get-CimInstance Win32_DiskDrive |
Select-Object Model, MediaType, InterfaceType, Size |
Format-Table -AutoSize | Out-File $OutFile -Append

"`nVOLUMES" | Out-File $OutFile -Append
Get-Volume |
Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size |
Format-Table -AutoSize | Out-File $OutFile -Append

"`nDUCKDB / TRAFFIC ANALYTICS PATHS" | Out-File $OutFile -Append
Get-ChildItem A:\TrafficAnalytics\DATA\SCATS\*.duckdb -ErrorAction SilentlyContinue |
Select-Object Name, @{Name="SizeGB";Expression={[math]::Round($_.Length/1GB,2)}}, LastWriteTime |
Format-Table -AutoSize | Out-File $OutFile -Append

"`nTEMP DRIVE" | Out-File $OutFile -Append
Get-ChildItem C:\DuckDBTemp -ErrorAction SilentlyContinue |
Measure-Object Length -Sum |
Select-Object @{Name="DuckDBTempSizeGB";Expression={[math]::Round($_.Sum/1GB,2)}} |
Format-List | Out-File $OutFile -Append

"`nPYTHON / PACKAGE VERSIONS" | Out-File $OutFile -Append
python --version 2>&1 | Out-File $OutFile -Append
python -c "import duckdb, pandas, matplotlib; print('duckdb', duckdb.__version__); print('pandas', pandas.__version__); print('matplotlib', matplotlib.__version__)" 2>&1 | Out-File $OutFile -Append

Write-Host "Report written to: $OutFile"