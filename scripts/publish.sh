# PyPI pe publish karne ke steps
# Run karo: bash scripts/publish.sh

set -e

echo "🐺 Lyncus — PyPI Publish Script"
echo "================================"

# 1. Clean old builds
echo "🧹 Old builds clean kar raha hoon..."
rm -rf dist/ build/ *.egg-info

# 2. Tests run karo
echo "🧪 Tests run kar raha hoon..."
python -m pytest tests/ -v --tb=short
if [ $? -ne 0 ]; then
    echo "❌ Tests fail ho gaye! Publish cancel."
    exit 1
fi

# 3. Build karo
echo "📦 Building wheel aur sdist..."
python -m build

# 4. Check karo
echo "🔍 Package check kar raha hoon..."
python -m twine check dist/*

# 5. TestPyPI pe pehle (optional)
echo ""
echo "TestPyPI pe publish karna chahte ho? (y/n)"
read -r response
if [ "$response" = "y" ]; then
    echo "🧪 TestPyPI pe upload kar raha hoon..."
    python -m twine upload --repository testpypi dist/*
    echo "✅ TestPyPI pe upload ho gaya!"
    echo "   Test karo: pip install -i https://test.pypi.org/simple/ Lyncus"
    echo ""
fi

# 6. Real PyPI pe publish
echo "🚀 PyPI pe publish karna chahte ho? (y/n)"
read -r response
if [ "$response" = "y" ]; then
    python -m twine upload dist/*
    echo ""
    echo "✅ Lyncus PyPI pe publish ho gaya!"
    echo "   Install karo: pip install Lyncus"
    echo "   PyPI link: https://pypi.org/project/Lyncus/"
fi
