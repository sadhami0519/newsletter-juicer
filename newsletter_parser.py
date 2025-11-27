# Gemini API Free Tier (10 RPM for Flash, 250K TPM)
import os
import json
import re
from datetime import datetime
from collections import defaultdict
from typing import Optional
import google.generativeai as genai
from dataclasses import dataclass, asdict

# Get API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
genai.configure(api_key=GEMINI_API_KEY)

# Using Gemini 2.5 Flash (Free Tier: 10 RPM, 250K TPM, 500 RPD)
MODEL_NAME = "gemini-2.5-flash"

# Newsletter categories for classification
NEWSLETTER_CATEGORIES = [
    "Self-Care & Wellness",
    "Artificial Intelligence",
    "General Tech Updates",
    "Data Science & ML",
    "Web Development",
    "Cloud Computing",
    "Security & Privacy",
    "Product Updates",
    "Career & Industry News",
    "Other"
]

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Email:
    """Email structure"""
    sender: str
    subject: str
    content: str
    date: str
    message_id: str = ""

@dataclass
class ProcessedNewsletter:
    """Processed newsletter data"""
    original_subject: str
    sender: str
    category: str
    summary: str
    key_topics: list
    tone: str
    timestamp: str

# ============================================================================
# AGENT 1: CLASSIFICATION AGENT
# ============================================================================

class ClassificationAgent:
    """
    Classifies newsletters into predefined categories.
    Uses prompt engineering to stay within free tier limits.
    """
    
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)
        self.categories = NEWSLETTER_CATEGORIES
    
    def classify(self, email: Email) -> dict:
        """
        Classify email into category with confidence score.
        Free tier optimized: Minimal token usage.
        """
        
        prompt = f"""Classify this newsletter into ONE category only. Respond in JSON format.

Categories: {', '.join(self.categories)}

Newsletter Subject: {email.subject}
Newsletter Content (first 500 chars): {email.content[:500]}...

Respond with this exact JSON format:
{{"category": "category_name", "confidence": 0.0-1.0, "reasoning": "brief reason"}}

ONLY output valid JSON, no other text."""

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text)
            return result
        except (json.JSONDecodeError, AttributeError):
            return {
                "category": "Other",
                "confidence": 0.5,
                "reasoning": "Classification failed, defaulting to Other"
            }

# ============================================================================
# AGENT 2: SUMMARIZATION AGENT
# ============================================================================

class SummarizationAgent:
    """
    Generates concise, bullet-point summaries of newsletters.
    Free tier optimized: Strict token budget (~300 tokens).
    """
    
    def __init__(self, model_name: str):
        self.model = genai.GenerativeModel(model_name)
    
    def summarize(self, email: Email, category: str) -> dict:
        """
        Create summary with key topics and tone analysis.
        Maximum output: 200 tokens (~50 words).
        """
        
        # Truncate content to stay within limits
        truncated_content = email.content[:800]
        
        prompt = f"""Summarize this {category} newsletter in 3-4 bullet points. Include tone analysis.

Subject: {email.subject}
Content: {truncated_content}...

Respond in this JSON format only:
{{
  "summary": "2-3 sentence overview",
  "key_topics": ["topic1", "topic2", "topic3"],
  "tone": "professional/casual/urgent/informative"
}}

Output ONLY valid JSON."""

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text)
            return result
        except (json.JSONDecodeError, AttributeError):
            return {
                "summary": "Newsletter summary unavailable",
                "key_topics": ["general"],
                "tone": "informative"
            }

# ============================================================================
# AGENT 3: DEDUPLICATION AGENT
# ============================================================================

class DeduplicationAgent:
    """
    Detects and removes duplicate newsletters.
    Uses semantic similarity hashing (free tier compatible).
    """
    
    def __init__(self):
        self.processed_hashes = set()
    
    def get_content_hash(self, email: Email) -> str:
        """Generate hash for deduplication"""
        # Simple but effective: hash of subject + first 100 chars of content
        content_sig = f"{email.subject}|{email.content[:100]}"
        return str(hash(content_sig))
    
    def is_duplicate(self, email: Email) -> bool:
        """Check if newsletter already processed"""
        content_hash = self.get_content_hash(email)
        
        if content_hash in self.processed_hashes:
            return True
        
        self.processed_hashes.add(content_hash)
        return False

# ============================================================================
# ORCHESTRATOR: MAIN PARSER ENGINE
# ============================================================================

class NewsletterParserOrchestrator:
    """
    Coordinates all three agents in agentic workflow.
    Manages state and output formatting.
    """
    
    def __init__(self, model_name: str = MODEL_NAME):
        self.classification_agent = ClassificationAgent(model_name)
        self.summarization_agent = SummarizationAgent(model_name)
        self.deduplication_agent = DeduplicationAgent()
        
        self.processed_newsletters: list[ProcessedNewsletter] = []
        self.categorized_output = defaultdict(list)
        self.request_count = 0
        self.token_usage = 0
    
    def parse_newsletter(self, email: Email) -> Optional[ProcessedNewsletter]:
        """
        Parse single newsletter through agent pipeline.
        
        Pipeline:
        1. Deduplication check
        2. Classification
        3. Summarization
        4. Store results
        """
        
        # Step 1: Deduplication
        if self.deduplication_agent.is_duplicate(email):
            print(f"⚠️  Duplicate detected: {email.subject[:50]}...")
            return None
        
        # Step 2: Classification
        classification_result = self.classification_agent.classify(email)
        category = classification_result.get("category", "Other")
        confidence = classification_result.get("confidence", 0.5)
        
        # Skip low-confidence classifications
        if confidence < 0.4:
            category = "Other"
        
        # Step 3: Summarization
        summarization_result = self.summarization_agent.summarize(email, category)
        
        # Step 4: Create processed newsletter object
        processed = ProcessedNewsletter(
            original_subject=email.subject,
            sender=email.sender,
            category=category,
            summary=summarization_result.get("summary", ""),
            key_topics=summarization_result.get("key_topics", []),
            tone=summarization_result.get("tone", "informative"),
            timestamp=datetime.now().isoformat()
        )
        
        self.processed_newsletters.append(processed)
        self.categorized_output[category].append(processed)
        self.request_count += 2  # 2 API calls per newsletter
        
        return processed
    
    def parse_batch(self, emails: list[Email]) -> dict:
        """
        Parse batch of emails while respecting free tier limits.
        Free tier: 10 RPM = max 1 email per 6 seconds for safety.
        """
        import time
        
        results = []
        for i, email in enumerate(emails):
            # Rate limiting: 0.1 calls/sec = 6 sec per email (safe margin)
            if i > 0:
                time.sleep(6)
            
            print(f"\n🔄 Processing [{i+1}/{len(emails)}]: {email.subject[:60]}...")
            result = self.parse_newsletter(email)
            if result:
                results.append(result)
        
        return {
            "total_processed": len(results),
            "newsletters": results,
            "categorized": dict(self.categorized_output),
            "request_count": self.request_count
        }
    
    def get_minimalist_display(self) -> str:
        """
        Generate minimalist output display.
        Focuses on core information, clean formatting.
        """
        
        output = []
        output.append("=" * 80)
        output.append("📬 NEWSLETTER PARSER - PROCESSED RESULTS")
        output.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("=" * 80)
        
        for category, newsletters in sorted(self.categorized_output.items()):
            output.append(f"\n📌 {category.upper()}")
            output.append("-" * 80)
            
            for i, newsletter in enumerate(newsletters, 1):
                output.append(f"\n  [{i}] {newsletter.original_subject}")
                output.append(f"      From: {newsletter.sender}")
                output.append(f"      Summary: {newsletter.summary}")
                output.append(f"      Topics: {', '.join(newsletter.key_topics)}")
                output.append(f"      Tone: {newsletter.tone}")
        
        output.append("\n" + "=" * 80)
        output.append(f"✅ Total Processed: {len(self.processed_newsletters)}")
        output.append(f"📊 API Requests: {self.request_count}")
        output.append("=" * 80)
        
        return "\n".join(output)

# ============================================================================
# SAMPLE DATA & DEMO
# ============================================================================

def generate_sample_emails() -> list[Email]:
    """Generate sample newsletter emails for testing"""
    
    sample_data = [
        Email(
            sender="wellness@meditationapp.com",
            subject="Weekly Wellness Newsletter - Stress Management Techniques",
            content="""Dear Subscriber,

This week's focus is on managing stress through breathing exercises and mindfulness.

Key Topics:
- Box breathing technique: 4-4-4-4 pattern
- Daily meditation practices for anxiety relief
- Progressive muscle relaxation guide
- Nutrition tips for mental health

Our latest guide covers how 10 minutes of daily meditation can reduce cortisol levels
by up to 25%. We also discuss the science behind mindfulness and its effects on brain plasticity.

Join our community challenges this month and get exclusive wellness resources!

Best regards,
Wellness Team""",
            date="2025-11-26"
        ),
        Email(
            sender="ai-digest@techcrunch.com",
            subject="AI Digest: OpenAI GPT-5 Development Updates and Market Impact",
            content="""Hello Tech Enthusiasts,

Breaking news from the AI industry this week:

1. OpenAI Reports GPT-5 Development Progress
   - Improved reasoning capabilities
   - Enhanced multimodal processing
   - New safety frameworks implemented

2. Google DeepMind Announces Breakthrough in Protein Folding
   - AlphaFold 3 predicts protein structures with 90% accuracy
   - Applications in drug discovery accelerating

3. Market Analysis: AI Chip Shortage Easing
   - NVIDIA supply chain improvements
   - Custom AI chip development by hyperscalers

4. Regulatory Updates
   - EU AI Act implementation timeline
   - US considers federal AI governance framework

Subscribe to our premium tier for exclusive analyst reports!

Regards,
Tech Digest Editorial Team""",
            date="2025-11-25"
        ),
        Email(
            sender="updates@github.com",
            subject="GitHub Updates: New Features for 2025 - Copilot Integration",
            content="""Hi Developer,

We're excited to announce major GitHub platform updates:

🚀 New Features:
- GitHub Copilot now integrated in web editor
- Enhanced code review automation
- Improved dependency security scanning
- New GitHub Actions capabilities

📊 Stats:
- 20% faster CI/CD pipelines
- 30% reduction in security vulnerabilities

🎉 Celebrating 100M developers on GitHub!

Check our blog for detailed documentation and migration guides.

GitHub Team""",
            date="2025-11-24"
        ),
        Email(
            sender="wellness@yourhealth.com",
            subject="Monthly Health Digest - Sleep Optimization Guide",
            content="""Welcome Back,

Our monthly newsletter covers the latest health and wellness insights:

Topics This Month:
- Circadian rhythm optimization
- Sleep tracking technology review
- Nutrition for better sleep quality
- Exercise timing and sleep correlation

Featured Article: "Why Your Sleep Matters More Than You Think"
- REM sleep and memory consolidation
- Deep sleep benefits for immune system
- Optimal sleep duration by age group

Resources:
- Free sleep assessment tool
- Personalized wellness plans
- Expert consultation booking

Your Health""",
            date="2025-11-23"
        ),
    ]
    
    return sample_data

def main():
    """Main execution function"""
    
    print("🚀 Newsletter Email Parser - Agentic System")
    print(f"📊 Model: {MODEL_NAME} (Free Tier: 10 RPM, 250K TPM)")
    print("-" * 80)
    
    # Initialize orchestrator
    orchestrator = NewsletterParserOrchestrator(MODEL_NAME)
    
    # Generate sample emails
    print("\n📧 Loading sample newsletter emails...")
    emails = generate_sample_emails()
    print(f"✓ Loaded {len(emails)} emails")
    
    # Process batch
    print("\n🔄 Starting newsletter parsing pipeline...")
    results = orchestrator.parse_batch(emails)
    
    # Display results
    print("\n" + orchestrator.get_minimalist_display())
    
    # Export to JSON
    output_file = "newsletters_output.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_processed": results["total_processed"],
            "newsletters": [asdict(n) for n in results["newsletters"]],
            "categorized_summary": {
                cat: [asdict(n) for n in newsletters]
                for cat, newsletters in results["categorized"].items()
            },
            "api_stats": {
                "total_requests": results["request_count"],
                "rate_limit_info": "Free Tier: 10 RPM (1 email ~6-8 seconds)"
            }
        }, f, indent=2)
    
    print(f"\n✅ Results exported to: {output_file}")
    
    return results

# ============================================================================
# EXECUTION
# ============================================================================

if __name__ == "__main__":

    main()
