"""
Setup Verification Script for Constitutional Content Guardian

Run this script to verify your environment is properly configured.
"""

import sys
import os


def check_python_version():
    """Check Python version >= 3.10"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[FAIL] Python {version.major}.{version.minor}.{version.micro} (Need 3.10+)")
        return False


def check_aws_credentials():
    """Check AWS credentials are configured"""
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"[OK] AWS credentials configured (Account: {identity['Account']})")
        return True
    except Exception as e:
        print(f"[FAIL] AWS credentials not configured: {e}")
        return False


def check_bedrock_access():
    """Check AWS Bedrock access"""
    try:
        import boto3
        client = boto3.client('bedrock-runtime', region_name='us-east-1')
        print("[OK] AWS Bedrock access verified")
        return True
    except Exception as e:
        print(f"[FAIL] AWS Bedrock access failed: {e}")
        return False


def check_required_files():
    """Check required project files exist"""
    required_files = [
        "requirements.txt",
        ".env.example",
        "src/models/bedrock_client.py",
        "src/config/prompts.py",
        "data/compliance_policies/hipaa_constitution.yaml"
    ]

    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"[OK] {file}")
        else:
            print(f"[FAIL] {file} (missing)")
            all_exist = False

    return all_exist


def test_bedrock_client():
    """Test Bedrock client functionality"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
        from models.bedrock_client import BedrockClient

        client = BedrockClient(region="us-east-1")
        print("[OK] Bedrock client initialized")

        # Test connection
        if client.test_connection():
            print("[OK] Bedrock connection test passed")
            return True
        else:
            print("[FAIL] Bedrock connection test failed")
            return False
    except Exception as e:
        print(f"[FAIL] Bedrock client test failed: {e}")
        return False


def main():
    print("Constitutional Content Guardian - Setup Verification\n")
    print("=" * 60)

    checks = [
        ("Python Version", check_python_version),
        ("AWS Credentials", check_aws_credentials),
        ("AWS Bedrock Access", check_bedrock_access),
        ("Required Files", check_required_files),
    ]

    results = []
    for name, check_func in checks:
        print(f"\n[CHECK] {name}:")
        results.append(check_func())

    # Optional: Test Bedrock client (may fail if dependencies not installed)
    print(f"\n[CHECK] Bedrock Client Test:")
    try:
        results.append(test_bedrock_client())
    except Exception as e:
        print(f"[SKIP] Skipped (install dependencies first): {e}")

    print("\n" + "=" * 60)

    if all(results):
        print("\n[SUCCESS] All checks passed! You're ready to build.")
        print("\nNext steps:")
        print("1. Run: pip install -r requirements.txt")
        print("2. Run: python -m spacy download en_core_web_sm")
        print("3. Create .env file with your AWS credentials")
        return 0
    else:
        print(f"\n[WARNING] {sum(not r for r in results)} check(s) failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
