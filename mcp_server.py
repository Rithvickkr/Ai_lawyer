from fastapi import FastAPI
import logging
import aiohttp
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="AI Lawyer MCP Server")

# Nebius AI Studio setup
NEBIUS_API_TOKEN = os.getenv("NEBIUS_API_TOKEN", "eyJhbGciOiJIUzI1NiIsImtpZCI6IlV6SXJWd1h0dnprLVRvdzlLZWstc0M1akptWXBvX1VaVkxUZlpnMDRlOFUiLCJ0eXAiOiJKV1QifQ.eyJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTI0NTkyNDY0MTk0ODI1NzEyOSIsInNjb3BlIjoib3BlbmlkIG9mZmxpbmVfYWNjZXNzIiwiaXNzIjoiYXBpX2tleV9pc3N1ZXIiLCJhdWQiOlsiaHR0cHM6Ly9uZWJpdXMtaW5mZXJlbmNlLmV1LmF1dGgwLmNvbS9hcGkvdjIvIl0sImV4cCI6MTkxNzE0NTgwMCwidXVpZCI6IjlkMDQ2YWM2LTU2OWUtNDFkYS1iYTg3LTA3Yzc2YTA0MmIwYSIsIm5hbWUiOiJhaWxhd3llcjIiLCJleHBpcmVzX2F0IjoiMjAzMC0wNi0wOVQwMzo0MzoyMSswMDAwIn0.goS3ZNUB8MTwxX6FVrvL9Ei_IbTaseMO4WcunDhxsis")
NEBIUS_API_URL = "https://api.studio.nebius.ai/v1/completions"

async def call_nebius(prompt: str, max_tokens: int = 1000):
    headers = {
        "Authorization": f"Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6IlV6SXJWd1h0dnprLVRvdzlLZWstc0M1akptWXBvX1VaVkxUZlpnMDRlOFUiLCJ0eXAiOiJKV1QifQ.eyJzdWIiOiJnb29nbGUtb2F1dGgyfDExNTI0NTkyNDY0MTk0ODI1NzEyOSIsInNjb3BlIjoib3BlbmlkIG9mZmxpbmVfYWNjZXNzIiwiaXNzIjoiYXBpX2tleV9pc3N1ZXIiLCJhdWQiOlsiaHR0cHM6Ly9uZWJpdXMtaW5mZXJlbmNlLmV1LmF1dGgwLmNvbS9hcGkvdjIvIl0sImV4cCI6MTkwNzE0NTgwMSwidXVpZCI6IjlkMDQ2YWM2LTU2OWUtNDFkYS1iYTg3LTA3Yzc2YTA0MmIwYSIsIm5hbWUiOiJhaWxhd3llcjIiLCJleHBpcmVzX2F0IjoiMjAzMC0wNi0wOFQxMDo0MzoyMSswMDAwIn0.goS3ZNUB8MTwxX6FVrvL9Ei_IbTaseMO4WcunDhxsis",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": 0.3  # Lower temperature for more factual responses
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(NEBIUS_API_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    text = result.get("choices", [{}])[0].get("text", "").strip()
                    # Clean up the response by removing any leading/trailing non-JSON characters
                    if text.startswith('*/'):
                        text = text[2:].strip()
                    if text.startswith('\n'):
                        text = text.strip()
                    logger.debug(f"Nebius response: {text}")
                    return text
                else:
                    error_text = await resp.text()
                    logger.error(f"Nebius API error: {resp.status} - {error_text}")
                    return ""
        except Exception as e:
            logger.error(f"Nebius API request failed: {e}")
            return ""

@app.get("/fetch_statute")
async def fetch_statute(jurisdiction: str, topic: str):
    logger.info(f"Fetching statute for {jurisdiction}, {topic}")
    try:
        prompt = f"""
        You are a legal expert with access to real legal information. Provide the actual statute or legal code for the jurisdiction '{jurisdiction}' on the topic '{topic}'. 
        
        Please provide:
        1. The exact statute number and citation
        2. The actual text of the law
        3. Any relevant subsections
        4. A clear explanation in layperson terms of what the law means and how it applies in practical situations
        
        Only provide real, existing legal information. If you don't have access to the specific statute, clearly state that and suggest where to find official sources.
        Ensure the response is formatted as follows:
        Format: [Jurisdiction] [Code/Statute] § [Number]: [Actual text]
        
        Then provide a "Plain English Explanation:" section that breaks down the legal language into simple, understandable terms for non-lawyers.
        """
        statute = await call_nebius(prompt, max_tokens=5000)
        if statute:
            return {"result": statute, "disclaimer": "This information is for educational purposes only. Always consult official legal sources and qualified attorneys for legal advice."}
        else:
            return {"result": f"Unable to retrieve statute information for {topic} in {jurisdiction}. Please consult official legal databases or an attorney."}
    except Exception as e:
        logger.error(f"Error fetching statute: {e}")
        return {"result": f"Error retrieving statute for {topic} in {jurisdiction}. Please consult official legal sources."}

@app.post("/analyze_contract")
async def analyze_contract(contract_text: str):
    logger.info("Analyzing contract")
    try:
        prompt = f"""
        You are a qualified legal expert. Analyze the following contract based on real legal principles and common contract law. Identify actual legal risks and standard contract clauses:
        
        Contract text: {contract_text}
        
        Please provide a real legal analysis including:
        1. Key clauses identification based on standard contract law
        2. Actual legal risks under applicable contract law
        3. Common legal issues that could arise
        4. Suggestions based on standard legal practice
        
        Base your analysis on real legal principles. If certain aspects require jurisdiction-specific analysis, note that.
        
        Format your response as JSON with "key_clauses", "legal_risks", "recommendations", and "jurisdiction_notes" arrays.
        """
        analysis = await call_nebius(prompt, max_tokens=3000)
        if analysis:
            # Try to parse the response, fallback to basic structure if parsing fails
            try:
                import json
                parsed = json.loads(analysis)
                parsed["disclaimer"] = "This analysis is for informational purposes only and does not constitute legal advice. Consult a qualified attorney for legal guidance."
                return parsed
            except:
                return {
                    "key_clauses": [analysis[:500] + "..." if len(analysis) > 500 else analysis],
                    "legal_risks": ["Full analysis provided in key_clauses section"],
                    "recommendations": ["Consult with a qualified attorney for comprehensive review"],
                    "disclaimer": "This analysis is for informational purposes only and does not constitute legal advice."
                }
        else:
            return {
                "key_clauses": ["Unable to analyze contract"], 
                "legal_risks": ["Analysis failed"],
                "recommendations": ["Please consult a qualified attorney"],
                "disclaimer": "Always seek professional legal advice for contract analysis."
            }
    except Exception as e:
        logger.error(f"Error analyzing contract: {e}")
        return {
            "key_clauses": ["Analysis error occurred"], 
            "legal_risks": ["Unable to process contract"],
            "recommendations": ["Consult a qualified attorney"],
            "disclaimer": "This service does not replace professional legal advice."
        }

@app.post("/generate_document")
async def generate_document(document_type: str, details: dict):
    logger.info(f"Generating {document_type}")
    try:
        prompt = f"""
        You are a legal expert. Create a real, legally sound {document_type} based on standard legal templates and current legal requirements. Use the following details: {details}
        
        The document should:
        1. Follow standard legal formatting for this document type
        2. Include all necessary legal clauses typically found in such documents
        3. Be based on real legal requirements and best practices
        4. Include appropriate legal language and terminology
        
        Provide a professional legal document that could be used as a starting template (though it should still be reviewed by an attorney).
        """
        document = await call_nebius(prompt, max_tokens=4000)
        return {
            "result": document,
            "disclaimer": "This document template is for informational purposes only. Have any legal document reviewed and customized by a qualified attorney before use.",
            "recommendation": "Always consult with a licensed attorney to ensure compliance with local laws and regulations."
        }
    except Exception as e:
        logger.error(f"Error generating document: {e}")
        return {
            "result": f"Unable to generate {document_type}. Please consult a qualified attorney for document preparation.",
            "disclaimer": "Professional legal assistance is recommended for all legal document preparation."
        }

if __name__ == "__main__":
    import uvicorn
    logger.info("Launching FastAPI MCP server on http://127.0.0.1:7860...")
    uvicorn.run(app, host="127.0.0.1", port=7860)