# Badger ICCID Pipeline — Setup

## 1. Copy zip to server (run on your local machine)
```
scp badger-deploy.zip user@server-ip:/home/user/
```

## 2. SSH into server
```
ssh user@server-ip
```

## 3. Unzip
```
unzip badger-deploy.zip
cd badgerOrderProcessing
```

## 4. Install Python and create virtual environment
```
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
```

## 5. Install dependencies
```
pip install -r requirements.txt
```

## 6. Install Salesforce CLI (one time)
```
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g @salesforce/cli
```

## 7. Run the app
```
uvicorn web_app:app --host 0.0.0.0 --port 8001
```

Open browser: http://server-ip:8001

## 8. Connect Salesforce
- Go to Admin page in the app
- Follow the 3-step Auth URL instructions to connect SF CLI

## Run in background (so it keeps running after SSH logout)
```
nohup uvicorn web_app:app --host 0.0.0.0 --port 8001 > log/app.log 2>&1 &
```

## Stop the app
```
pkill -f "uvicorn web_app:app"
```
