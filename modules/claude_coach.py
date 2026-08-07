"""
GranskningsCoach - AI-driven assistant for municipal financial investigation.
Uses Claude Sonnet with web search capabilities.
"""
import os
from pathlib import Path
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

class GranskningsCoach:
    """
    AI coach that helps journalists investigate municipal company finances.
    Provides guidance based on Swedish public records law and case studies.
    """
    
    def __init__(self, knowledge_path: Optional[str] = None):
        """
        Initialize the coach with Claude API and knowledge base.
        
        Args:
            knowledge_path: Path to knowledge base directory (markdown files)
        """
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-20250514"
        self.knowledge_base = ""
        
        if knowledge_path:
            self.load_knowledge_base(knowledge_path)
        else:
            # Default: load from knowledge/ directory relative to this file
            default_path = Path(__file__).parent.parent / "knowledge"
            if default_path.exists():
                self.load_knowledge_base(str(default_path))
    
    def load_knowledge_base(self, path: str):
        """
        Load all markdown files from knowledge directory into memory.
        
        Args:
            path: Directory containing .md knowledge files
        """
        knowledge_dir = Path(path)
        if not knowledge_dir.exists():
            return
        
        texts = []
        for md_file in knowledge_dir.glob("*.md"):
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                texts.append(f"## {md_file.stem}\n\n{content}")
        
        self.knowledge_base = "\n\n---\n\n".join(texts)
    
    def _get_system_prompt(self) -> str:
        """Generate system prompt with knowledge base context."""
        base_prompt = """Du är Granskning-Coach, en AI-assistent specialiserad på att hjälpa journalister 
granska kommunala bolag och deras ekonomi i Sverige.

Din expertis inkluderar:
- Offentlighetsprincipen och Tryckfrihetsförordningen kap 2
- BAS-kontoplan och bokföringsanalys
- Kommunala bolag och deras skyldigheter
- Granskningsjournalistik med fokus på kommunal verksamhet

Du har kunskap om tidigare avslöjanden och varningssignaler:
- MIPIM-skandalen i Karlshamn
- Representation och resekostnader
- Uppdelade inköp för att kringgå upphandling
- Konsultavtal och intressekonflikter

Var pedagogisk och förklara juridiska koncept enkelt. Ge konkreta tips.
Om du inte är säker på något, be om mer information eller föreslå hur användaren kan ta reda på det."""

        if self.knowledge_base:
            return f"{base_prompt}\n\n# KUNSKAPSBAS\n\n{self.knowledge_base}"
        return base_prompt
    
    def ask(self, question: str, context: str = "") -> str:
        """
        Ask the coach a question about municipal finances or investigation.
        
        Args:
            question: User's question
            context: Optional context (e.g., current data being analyzed)
            
        Returns:
            Coach's response as string
        """
        messages = []
        
        if context:
            messages.append({
                "role": "user",
                "content": f"KONTEXT:\n{context}\n\n---\n\nFRÅGA: {question}"
            })
        else:
            messages.append({
                "role": "user",
                "content": question
            })
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self._get_system_prompt(),
                messages=messages
            )
            return response.content[0].text
        except anthropic.APIError as e:
            return f"Fel vid anrop till AI: {str(e)}"
    
    def research_supplier(self, company_name: str) -> str:
        """
        Research a supplier/company using web search to find potential red flags.
        
        Args:
            company_name: Name of company to research
            
        Returns:
            Research summary with findings
        """
        search_prompt = f"""Sök information om företaget "{company_name}" och sammanfatta:

1. **Grundfakta**: Organisationsnummer, bransch, antal anställda, omsättning
2. **Ägare och styrelse**: Vilka personer är involverade?
3. **Kopplingar**: Har någon i styrelsen koppling till kommunal verksamhet?
4. **Nyheter**: Har företaget förekommit i nyhetsrapportering?
5. **Varningsflaggor**: Konkurser, skatteskulder, omdiskuterade affärer

Fokusera särskilt på eventuella kopplingar till Karlshamns kommun eller kommunala bolag.
Var tydlig med källorna för din information."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5
                }],
                messages=[{
                    "role": "user",
                    "content": search_prompt
                }]
            )
            
            # Extract text from response
            result_parts = []
            for block in response.content:
                if hasattr(block, 'text'):
                    result_parts.append(block.text)
            
            return "\n".join(result_parts) if result_parts else "Ingen information hittades."
            
        except anthropic.APIError as e:
            return f"Fel vid leverantörssökning: {str(e)}"
    
    def analyze_transaction(self, transaction_data: dict) -> str:
        """
        Analyze a specific transaction for potential issues.
        
        Args:
            transaction_data: Dict with keys like 'belopp', 'konto', 'leverantör', 'datum', 'beskrivning'
            
        Returns:
            Analysis with risk assessment
        """
        prompt = f"""Analysera följande transaktion från ett kommunalt bolag:

**Datum**: {transaction_data.get('datum', 'Okänt')}
**Belopp**: {transaction_data.get('belopp', 'Okänt')} kr
**Konto**: {transaction_data.get('konto', 'Okänt')} - {transaction_data.get('kontonamn', '')}
**Leverantör**: {transaction_data.get('leverantör', 'Okänd')}
**Beskrivning**: {transaction_data.get('beskrivning', 'Ingen')}

Besvara:
1. Är detta konto känsligt ur granskningssynpunkt?
2. Finns det något ovanligt med beloppet eller beskrivningen?
3. Behöver vi mer information för att bedöma transaktionen?
4. Föreslå uppföljningsfrågor till bolaget.

Risknivå (1-5): Ange en siffra och motivera kort."""

        return self.ask(prompt)
    
    def generate_request_letter(self, 
                                 company_name: str,
                                 document_types: list[str],
                                 date_range: tuple[str, str] = None,
                                 specific_accounts: list[str] = None) -> str:
        """
        Generate a formal request letter for public documents.
        
        Args:
            company_name: Name of the municipal company
            document_types: List of document types to request
            date_range: Optional tuple (from_date, to_date)
            specific_accounts: Optional list of account numbers
            
        Returns:
            Formatted request letter
        """
        docs_formatted = "\n".join(f"- {doc}" for doc in document_types)
        
        date_text = ""
        if date_range:
            date_text = f"för perioden {date_range[0]} till {date_range[1]}"
        
        accounts_text = ""
        if specific_accounts:
            accounts_text = f"\n\nSpecifikt efterfrågas transaktioner på följande konton: {', '.join(specific_accounts)}"
        
        prompt = f"""Generera ett formellt brev för att begära ut allmänna handlingar enligt 
Tryckfrihetsförordningen 2 kap. från {company_name}.

Handlingar som ska begäras:
{docs_formatted}

Tidsperiod: {date_text if date_text else 'Senaste räkenskapsåret'}
{accounts_text}

Brevet ska:
1. Vara korrekt enligt TF 2 kap (kräv inte motivering)
2. Be om digital kopia om möjligt (Excel-format för ekonomidata)
3. Hänvisa till skyndsam hantering enligt lag
4. Vara professionellt men bestämt
5. Inkludera kontaktuppgifter (placeholder)

Formatera brevet klart för utskrift."""

        return self.ask(prompt)
    
    def explain_account(self, account_number: str) -> str:
        """
        Explain what a BAS account is used for and why it might be interesting.
        
        Args:
            account_number: BAS account number (e.g., "6071")
            
        Returns:
            Explanation of the account
        """
        prompt = f"""Förklara BAS-konto {account_number}:

1. Vad används kontot för?
2. Vilken kontoklass tillhör det?
3. Varför kan det vara intressant att granska?
4. Vilka varningssignaler bör man leta efter?
5. Ge exempel på misstänkta transaktioner.

Var pedagogisk - förklara för någon utan bokföringskunskap."""

        return self.ask(prompt)


# Quick test
if __name__ == "__main__":
    coach = GranskningsCoach()
    print("Testing GranskningsCoach...")
    
    # Test basic question
    response = coach.ask("Vad är en rimlig gräns för representation?")
    print(f"\nFråga om representation:\n{response[:500]}...")
