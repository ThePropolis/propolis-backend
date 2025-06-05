# propolis-backend

## How the backend is currently configured. 

Currently, the backend sits on EC2 with a publiclly accessible url https://propolis-dashboard.com. In the future these values should be authenticated so they aren't public to everyone else. This takes some basic configuration.

At the moment, the way to update the backend code is manually. You have to log into 
EC2 and use this command:

ssh -i propolis-key.pem ec2-user@44.211.130.121.

Ask for the key from Dilan. From there, there is the propolis-backend code that is cloned from this repistory. At the moment, there is no way to push or pull. In the future, I would like to have it such that when you push to the backend on github, it automatically pushes to EC2. 

Updating the code for now is tricky. You are going to need to rebuild the docker containter and rerun docker.



## Env Configuration

GUESTY_SECRET=

GUESTY_CLIENT_ID=

SUPABASE_URL=

SUPABASE_KEY=

SECRET_KEY=

DOORLOOP_API_KEY=