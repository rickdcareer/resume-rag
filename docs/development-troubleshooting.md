# Development & Troubleshooting Guide

## Common Issues and Solutions

### Git Diff Review Issues

**Problem**: When reviewing large git diffs (300+ lines), standard `git diff` commands hang or get stuck in the terminal pager.

**Solution**: Use the git diff capture utility:
1. Create temporary files to capture git output without paging issues
2. Use `git --no-pager diff > temp_file.txt` to bypass terminal pager
3. Read the captured files directly instead of streaming output

**Files added to .gitignore**:
- `temp_*.txt` - temporary git diff capture files
- `temp_git_review.txt` - git review output files

### OpenAI Client Issues

**Problem**: `TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`

**Root Cause**: OpenAI library version 1.12.0 requires `httpx < 0.27`, but container had `httpx 0.28.1`

**Solution**: 
```bash
# Inside container
podman exec resume-api pip install 'httpx<0.27'
podman restart resume-api
```

**Fix Applied**: Downgrade httpx from 0.28.1 to 0.26.0 in container

### Resume Chunking Issues

**Problem**: Resumes being processed as single large chunks instead of meaningful sections

**Root Cause**: 
- Original `clean_text()` function flattened all structure
- Basic splitting algorithm didn't understand resume sections

**Solution**: Complete rewrite of chunking algorithm with:
- Section-aware splitting (EXPERIENCE, EDUCATION, etc.)
- Structure-preserving text cleaning
- Fallback chunking strategies
- Comprehensive logging for debugging

### WSL/Podman Networking Issues

**Problem**: API running in WSL container not accessible from Windows host

**Symptoms**:
- `curl http://localhost:8000/health` fails from Windows
- `wsl -d Ubuntu -e bash -c "curl http://localhost:8000/health"` works from WSL
- `netstat -an | findstr :8000` shows wslrelay listening

**Solution**:
```powershell
# Restart WSL to reset networking
wsl --shutdown
# Restart containers
```

**Prevention**: Document this known WSL networking quirk in setup instructions

### Chunk Duplication Issues

**Problem**: Same resume chunks appearing multiple times in output

**Root Cause**: 
- No deduplication in citation collection
- Output generation repeating chunks
- Console display not filtering duplicates

**Solution**: Added deduplication at multiple levels:
- `generation.py`: Deduplicate cited chunks before returning results
- `smoke_demo.py`: Deduplicate chunks in both file output and console display
- Use `list(dict.fromkeys())` to preserve order while removing duplicates

### Database Cleanup for Development

**Problem**: Stale resume data causing chunking algorithm testing issues

**Solution**: Created `scripts/clear_database.py` utility:
- Clears all resume and chunk data
- Resets auto-increment counters  
- Requires confirmation prompt for safety
- Use `--confirm` flag to skip prompt for automation

```bash
# Interactive cleanup
python scripts/clear_database.py

# Auto-confirmed cleanup
python scripts/clear_database.py --confirm
```

## Development Workflow

### Making Large Changes

1. **Before making changes**: Run smoke test to establish baseline
2. **During development**: Use extensive logging to trace execution
3. **After changes**: Clear database if data model/chunking changed
4. **Testing**: Run smoke test to verify end-to-end functionality
5. **Committing**: Use git diff capture utility for large change reviews

### Debugging Checklist

1. **API not starting**: Check WSL status, restart if needed
2. **Chunking issues**: Check logs for section splitting and word counts
3. **OpenAI errors**: Verify httpx version compatibility  
4. **Duplicate chunks**: Check deduplication logic in generation and display
5. **Stale data**: Clear database and re-upload test data

### Container Management

```bash
# Check container status
wsl -d Ubuntu -e bash -c "podman ps"

# View container logs
wsl -d Ubuntu -e bash -c "podman logs resume-api"

# Restart container
wsl -d Ubuntu -e bash -c "podman restart resume-api"

# Check package versions inside container
wsl -d Ubuntu -e bash -c "podman exec resume-api pip show openai httpx"
```

## Code Review Process

### Large Changesets

For commits with 200+ line changes:
1. Use git diff capture utility to avoid terminal hanging
2. Review each service layer change systematically
3. Verify no secrets/API keys in diff files
4. Update documentation for any new issues discovered
5. Test end-to-end functionality before committing

### Security Review

Always check for accidentally committed secrets:
- API keys (sk-*, sk-proj-*)
- Database URLs with credentials
- Environment variables with sensitive data
- Container logs with exposed credentials

Use `.gitignore` patterns to prevent common leaks:
- `*.env*` files
- `secrets/` directory
- `temp_*.txt` files from development
