# Run all three Flask apps simultaneously (Windows PowerShell)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Multi-DB Flask Demo - Starting All Applications" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Store the base path
$basePath = $PSScriptRoot

# Start Product App (Port 5001)
Write-Host "Starting Product App (Azure SQL) on port 5001..." -ForegroundColor Blue
$product = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$basePath\product_app'; python app.py" -PassThru

Start-Sleep -Seconds 2

# Start Order App (Port 5002)
Write-Host "Starting Order App (PostgreSQL) on port 5002..." -ForegroundColor Green
$order = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$basePath\order_app'; python app.py" -PassThru

Start-Sleep -Seconds 2

# Start Logistics App (Port 5003)
Write-Host "Starting Logistics App (MongoDB) on port 5003..." -ForegroundColor Yellow
$logistics = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$basePath\logistics_app'; python app.py" -PassThru

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  All applications started!" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Access the applications at:" -ForegroundColor White
Write-Host "    * Product App (Azure SQL):  " -NoNewline; Write-Host "http://localhost:5001" -ForegroundColor Blue
Write-Host "    * Order App (PostgreSQL):   " -NoNewline; Write-Host "http://localhost:5002" -ForegroundColor Green
Write-Host "    * Logistics App (MongoDB):  " -NoNewline; Write-Host "http://localhost:5003" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Close the terminal windows to stop the applications" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
