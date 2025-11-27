import os
import sys
import subprocess

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"✨ {text}")
    print("="*80)

def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python Version")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    
    print("✅ Python version OK")
    return True

def check_api_key():
    """Check if API key is set"""
    print_header("Checking Gemini API Key")
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        print("\nTo set API key:")
        print("  Linux/macOS: export GEMINI_API_KEY='your_key_here'")
        print("  Windows: set GEMINI_API_KEY=your_key_here")
        print("\nGet your key at: https://aistudio.google.com/apikey")
        return False
    
    # Show masked key for security
    masked = api_key[:10] + "*" * (len(api_key)-20) + api_key[-10:]
    print(f"✅ API Key set: {masked}")
    return True

def install_dependencies():
    """Install required packages"""
    print_header("Installing Dependencies")
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"
        ])
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def test_import():
    """Test if google-generativeai can be imported"""
    print_header("Testing Imports")
    
    try:
        import google.generativeai as genai
        print("✅ google-generativeai imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def run_demo():
    """Run demo with sample data"""
    print_header("Running Demo")
    
    try:
        exec(open("newsletter_parser.py").read())
    except FileNotFoundError:
        print("❌ newsletter_parser.py not found in current directory")
        return False
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        return False
    
    return True

def main():
    """Main quick-start flow"""
    
    print("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║         🚀 NEWSLETTER EMAIL PARSER - QUICK START                      ║
    ║                                                                       ║
    ║  Multi-Agent Agentic System using Gemini 2.5 Flash (Free Tier)       ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    checks = [
        ("Python Version", check_python_version()),
        ("API Key", check_api_key()),
        ("Dependencies", install_dependencies()),
        ("Import Test", test_import()),
    ]
    
    all_passed = all(status for _, status in checks)
    
    print("\n" + "="*80)
    print("📊 SETUP CHECK SUMMARY")
    print("="*80)
    for check_name, status in checks:
        symbol = "✅" if status else "❌"
        print(f"{symbol} {check_name}")
    print("="*80)
    
    if all_passed:
        print("\n✨ All checks passed! Ready to run.")
        response = input("\nRun demo with sample newsletters? (y/n): ").strip().lower()
        if response == 'y':
            run_demo()
    else:
        print("\n❌ Some checks failed. Please fix the issues above and try again.")
        sys.exit(1)

if __name__ == "__main__":

    main()
