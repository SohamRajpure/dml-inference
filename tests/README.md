# Install dependancies
sudo apt install python3-pytest python3-pytest-cov

# Run all tests
pytest tests/ --cov=src.cluster --cov-report=term-missing

# Run specific test file
pytest tests/cluster/<specific_test_file> -v