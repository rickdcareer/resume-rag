"""Generation service for rewriting resume chunks using GPT-4o."""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from openai import OpenAI
except ImportError as e:
    raise ImportError(
        "OpenAI package not installed. Please run: pip install openai>=1.12"
    ) from e

from config import config
from app.services.retrieval import RetrievalResult

logger = logging.getLogger(__name__)

@dataclass
class GenerationResult:
    """Container for generation results."""
    
    tailored_bullets: List[str]
    cited_chunks: List[int]
    original_chunk_count: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tailored_bullets": self.tailored_bullets,
            "cited_chunks": self.cited_chunks,
            "original_chunk_count": self.original_chunk_count,
            "metadata": self.metadata
        }

class ResumeGenerator:
    """GPT-4o powered resume generation service."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the generator with OpenAI client.
        
        Args:
            api_key: OpenAI API key (will use config.OPENAI_API_KEY if not provided)
        """
        # Get API key from parameter or config
        self.api_key = api_key or config.OPENAI_API_KEY
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is required. Please set OPENAI_API_KEY environment variable "
                "or pass api_key parameter to ResumeGenerator(). "
                "Get your API key from: https://platform.openai.com/api-keys"
            )
        
        # Initialize OpenAI client with latest API only
        try:
            from openai import OpenAI
            
            # Check if there are any environment variables causing issues
            import os
            proxy_vars = {k: v for k, v in os.environ.items() if 'proxy' in k.lower()}
            if proxy_vars:
                logger.warning(f"Found proxy environment variables: {proxy_vars}")
            
            # Initialize with minimal parameters - latest OpenAI client only
            self.client = OpenAI(api_key=self.api_key)
            logger.info("✅ OpenAI client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error args: {e.args}")
            raise RuntimeError(f"Cannot initialize OpenAI client: {e}")
        self.model = config.OPENAI_MODEL
        self.temperature = config.OPENAI_TEMPERATURE
        self.max_tokens = config.OPENAI_MAX_TOKENS
        
        logger.info(f"✅ ResumeGenerator initialized with {self.model}")
    
    def rewrite_chunks(
        self,
        chunks: List[RetrievalResult],
        job_description: str,
        max_bullets: int = 8,
        style: str = "professional"
    ) -> GenerationResult:
        """
        Rewrite resume chunks into tailored bullets for a specific job.
        
        Args:
            chunks: List of retrieved resume chunks with similarity scores
            job_description: Target job description for tailoring
            max_bullets: Maximum number of bullets to generate
            style: Writing style ('professional', 'concise', 'impact')
            
        Returns:
            GenerationResult with tailored bullets and citations
            
        Raises:
            ValueError: If no chunks provided or job description empty
            RuntimeError: If OpenAI API call fails
        """
        if not chunks:
            raise ValueError("No chunks provided for rewriting")
        
        if not job_description.strip():
            raise ValueError("Job description cannot be empty")
        
        logger.info(f"Rewriting {len(chunks)} chunks for job description ({len(job_description)} chars)")
        
        try:
            # Prepare chunk context for GPT-4o
            chunk_context = self._prepare_chunk_context(chunks)
            
            # Create the system prompt
            system_prompt = self._create_system_prompt(style)
            
            # Create the user prompt
            user_prompt = self._create_user_prompt(chunk_context, job_description, max_bullets)
            
            logger.info(f"Calling GPT-4o with {len(chunk_context)} chunks")
            
            # Call OpenAI API with config settings
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=0.9
            )
            
            # Extract and parse the response
            generated_text = response.choices[0].message.content
            
            if not generated_text:
                raise RuntimeError("GPT-4o returned empty response")
            
            # Parse the bullets and citations
            bullets, cited_chunks = self._parse_generated_response(generated_text, chunks)
            
            # Deduplicate cited chunks to avoid repetition in output
            unique_cited_chunks = list(dict.fromkeys(cited_chunks))  # Preserves order while removing duplicates
            
            result = GenerationResult(
                tailored_bullets=bullets,
                cited_chunks=unique_cited_chunks,
                original_chunk_count=len(chunks),
                metadata={
                    "model": self.model,
                    "style": style,
                    "max_bullets": max_bullets,
                    "job_description_length": len(job_description),
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
            )
            
            logger.info(f"✅ Generated {len(bullets)} bullets citing {len(unique_cited_chunks)} unique chunks (from {len(cited_chunks)} total citations)")
            return result
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            raise RuntimeError(f"Failed to generate tailored resume: {str(e)}")
    
    def _prepare_chunk_context(self, chunks: List[RetrievalResult]) -> Dict[str, str]:
        """Prepare chunks for GPT-4o context with chunk IDs."""
        chunk_context = {}
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"C{i+1}"
            chunk_context[chunk_id] = chunk.chunk_text
        
        return chunk_context
    
    def _create_system_prompt(self, style: str) -> str:
        """Create the system prompt for GPT-4o."""
        style_instructions = {
            "professional": "Write in a professional, polished tone with strong action verbs.",
            "concise": "Write concisely with maximum impact in minimum words.",
            "impact": "Focus on quantifiable achievements and business impact."
        }
        
        style_instruction = style_instructions.get(style, style_instructions["professional"])
        
        return f"""You are an expert resume writer specializing in tailoring resumes to specific job descriptions.

Your task is to rewrite resume content chunks into compelling bullet points that are highly relevant to a target job description.

CRITICAL REQUIREMENTS:
1. **Stay factual**: Only use information present in the provided chunks - never invent or embellish
2. **Cite sources**: End each bullet with [C1], [C2], etc. to reference the chunk(s) used
3. **Match job keywords**: Incorporate relevant keywords and phrases from the job description
4. **{style_instruction}**
5. **Use bullet format**: Start each line with •
6. **Prioritize relevance**: Focus on the most job-relevant content first

OUTPUT FORMAT:
• [Tailored bullet point based on chunk content] [C1]
• [Another bullet point possibly combining chunks] [C1, C2]
• [Continue with most relevant content] [C3]

Remember: Every bullet MUST cite at least one chunk ID, and every fact MUST come from the provided chunks."""
    
    def _create_user_prompt(self, chunk_context: Dict[str, str], job_description: str, max_bullets: int) -> str:
        """Create the user prompt with chunks and job description."""
        # Format chunks for the prompt
        chunks_text = "\n\n".join([
            f"**{chunk_id}**: {content}"
            for chunk_id, content in chunk_context.items()
        ])
        
        return f"""**JOB DESCRIPTION:**
{job_description}

**RESUME CHUNKS TO REWRITE:**
{chunks_text}

**INSTRUCTIONS:**
Rewrite the resume chunks into {max_bullets} compelling bullet points that are highly relevant to this job description. 

Each bullet must:
- Start with •
- Be tailored to match the job requirements
- End with citation tags like [C1] or [C1, C2]
- Only use facts from the provided chunks
- Use strong action verbs and quantifiable results where available

Focus on the most job-relevant content first. If chunks overlap, combine them intelligently."""
    
    def _parse_generated_response(self, response: str, chunks: List[RetrievalResult]) -> tuple[List[str], List[int]]:
        """Parse GPT-4o response to extract bullets and citations."""
        bullets = []
        all_cited_chunks = []
        
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                # Extract the bullet text and citations
                bullet_text = line
                
                # Find citation tags [C1], [C2], etc.
                import re
                citation_pattern = r'\[C(\d+)\]'
                citations = re.findall(citation_pattern, line)
                
                if citations:
                    # Convert to chunk indices (C1 -> 0, C2 -> 1, etc.)
                    chunk_indices = [int(c) - 1 for c in citations if int(c) <= len(chunks)]
                    all_cited_chunks.extend(chunk_indices)
                    
                    bullets.append(bullet_text)
        
        # If no bullets found, try to extract any lines that look like bullets
        if not bullets:
            for line in lines:
                line = line.strip()
                if line and len(line) > 10:  # Reasonable bullet length
                    bullets.append(f"• {line}")
                    # Assume it uses the first chunk if no citations found
                    all_cited_chunks.append(0)
        
        return bullets, all_cited_chunks

# Global generator instance (initialized on first use)
_generator_instance = None

def get_generator() -> ResumeGenerator:
    """Get or create the global generator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = ResumeGenerator()
    return _generator_instance

def rewrite_chunks(
    chunks: List[RetrievalResult],
    job_description: str,
    max_bullets: int = 8,
    style: str = "professional"
) -> GenerationResult:
    """
    Convenience function to rewrite chunks using the global generator.
    
    Args:
        chunks: List of retrieved resume chunks
        job_description: Target job description
        max_bullets: Maximum number of bullets to generate
        style: Writing style ('professional', 'concise', 'impact')
        
    Returns:
        GenerationResult with tailored bullets and citations
    """
    generator = get_generator()
    return generator.rewrite_chunks(chunks, job_description, max_bullets, style)

# Test function for REPL usage
def test_generation(
    sample_chunks: Optional[List[str]] = None,
    job_description: Optional[str] = None
) -> GenerationResult:
    """
    Test function for REPL usage.
    
    Args:
        sample_chunks: Optional list of sample chunk texts
        job_description: Optional job description (uses default if None)
        
    Returns:
        GenerationResult from test generation
    """
    # Default test data
    if sample_chunks is None:
        sample_chunks = [
            "Led development of web applications using Python Flask and React, serving 10,000+ daily users",
            "Built machine learning models using scikit-learn and TensorFlow for customer behavior prediction",
            "Managed a team of 3 junior developers and conducted code reviews for quality assurance",
            "Implemented CI/CD pipelines using Jenkins and Docker, reducing deployment time by 60%"
        ]
    
    if job_description is None:
        job_description = """
        Senior Full Stack Developer needed for fast-growing startup. Must have experience with:
        - Python and modern web frameworks (Flask/FastAPI)
        - Frontend development with React
        - Machine learning and data science
        - Team leadership and mentoring
        - DevOps and deployment automation
        We value candidates who can work in fast-paced environments and deliver high-quality solutions.
        """
    
    # Convert sample chunks to RetrievalResult objects
    mock_chunks = []
    for i, chunk_text in enumerate(sample_chunks):
        result = RetrievalResult(
            chunk_id=i + 1,
            resume_id=1,
            chunk_text=chunk_text,
            distance=0.1 + i * 0.05,  # Mock similarity scores
            metadata={"test": True}
        )
        mock_chunks.append(result)
    
    print(f"🧪 Testing generation with {len(mock_chunks)} chunks")
    print(f"Job description: {job_description[:100]}...")
    
    try:
        result = rewrite_chunks(
            chunks=mock_chunks,
            job_description=job_description,
            max_bullets=5,
            style="professional"
        )
        
        print(f"\n✅ Generated {len(result.tailored_bullets)} bullets:")
        for i, bullet in enumerate(result.tailored_bullets, 1):
            print(f"  {i}. {bullet}")
        
        print(f"\n📊 Cited chunks: {result.cited_chunks}")
        print(f"🔧 Metadata: {result.metadata}")
        
        return result
        
    except Exception as e:
        print(f"❌ Generation test failed: {e}")
        raise

if __name__ == "__main__":
    # This part is for testing the generation service directly
    print("🧪 Testing GPT-4o generation service...")
    test_generation()
