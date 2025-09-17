# Unit Filtering Deployment Troubleshooting Guide

## Issue: Unit Filtering Works Locally But Not in Deployment

### Quick Diagnosis Steps

1. **Check Database Health**
   ```bash
   curl https://propolis-dashboard.com/db/health-check
   ```
   This will show:
   - Environment variable status
   - Database table accessibility
   - Available properties in the database

2. **Test Unit Filtering Endpoint**
   ```bash
   curl "https://propolis-dashboard.com/db/units-for-property?property=YourPropertyName"
   ```
   Look for debug information in the response.

### Common Issues and Solutions

#### 1. Environment Variables Not Set
**Symptoms:** Database connection errors, empty responses
**Solution:** 
- Ensure `.env` file exists in deployment
- Verify environment variables are set:
  ```bash
  SUPABASE_URL=your_supabase_url
  SUPABASE_KEY=your_supabase_key
  ```

#### 2. Database Tables Missing
**Symptoms:** "Table not found" errors
**Solution:**
- Verify tables `STR-Jul-2025` and `Rent-Paid-July-2025` exist in Supabase
- Check table permissions for the service key

#### 3. Property Name Mismatch
**Symptoms:** No results returned, but database has data
**Solution:**
- Check the actual property names in the database using the health check endpoint
- Verify the property name parsing logic matches your data format

#### 4. Docker Environment Issues
**Symptoms:** Environment variables not loading
**Solution:**
- Use Docker environment variables instead of `.env` file:
  ```bash
  docker run -e SUPABASE_URL=... -e SUPABASE_KEY=... your-image
  ```

### Debugging Commands

1. **Check Environment Variables**
   ```bash
   # SSH into EC2
   ssh -i propolis-key.pem ec2-user@44.211.130.121
   
   # Check if .env file exists and has correct values
   cat .env
   ```

2. **Check Docker Container**
   ```bash
   # List running containers
   docker ps
   
   # Check container logs
   docker logs <container_id>
   
   # Execute commands in container
   docker exec -it <container_id> /bin/bash
   ```

3. **Test Database Connection**
   ```bash
   # From inside container
   python -c "
   import os
   from supabase import create_client
   from dotenv import load_dotenv
   load_dotenv()
   print('SUPABASE_URL:', bool(os.getenv('SUPABASE_URL')))
   print('SUPABASE_KEY:', bool(os.getenv('SUPABASE_KEY')))
   client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
   print('Connection test:', client.table('STR-Jul-2025').select('*').limit(1).execute())
   "
   ```

### Deployment Steps

1. **Update Code on EC2**
   ```bash
   ssh -i propolis-key.pem ec2-user@44.211.130.121
   cd propolis-backend
   git pull origin main
   ```

2. **Rebuild Docker Container**
   ```bash
   docker build -t propolis-backend .
   docker stop $(docker ps -q --filter ancestor=propolis-backend)
   docker run -d -p 8000:8000 --env-file .env propolis-backend
   ```

3. **Verify Deployment**
   ```bash
   curl https://propolis-dashboard.com/health
   curl https://propolis-dashboard.com/db/health-check
   ```

### Monitoring

- Check application logs: `docker logs <container_id>`
- Monitor health endpoint: `https://propolis-dashboard.com/health`
- Use database health check: `https://propolis-dashboard.com/db/health-check`

### Emergency Rollback

If deployment fails:
```bash
# Stop current container
docker stop $(docker ps -q --filter ancestor=propolis-backend)

# Run previous working version
docker run -d -p 8000:8000 --env-file .env <previous_image_tag>
```
