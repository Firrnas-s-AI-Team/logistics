from typing import List, Dict, Optional
def generate_email_content(client,shipment_details: str) -> str:
    prompt = f"""
    Write a professional and concise email body based on the following shipment details:
    Shipment Details:
    
    {shipment_details}

    The email should:
    1. Be clear and professional strickly start with Dear, only.
    2. Include shipment details.
    3. Request handling capability and rate quotation.
    4. End **strickly** with the following text, without any modifications:

     Thanks and best regards,

    Mai Mohamed

    Logistics Executive

    Mobica for Integrated Industries

    Address:

    (1)    3rd Industrial Zone, 6th of October City, Giza, Egypt  
    (2)    KM28 Cairo-Alex Desert Rd., Abu Rawash, Giza, Egypt  

    Mobile: (+20) 1066653810  
    Hotline: 16992  
    Email: mai.mohamed@mobica.net  
    Website: www.mobica.net  
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", 
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating email: {e}")
        return f"""
        Dear ,

        We would like to request a quotation for our company. Please find the shipment details below:

        Shipment Details:
        {shipment_details}

        Kindly provide your quotation offer, including your handling capabilities and rates. If you require any additional details to process the quote, please feel free to reach out.

        Thank you, and I look forward to your response.

        Best regards,

        Mai Mohamed

        Logistics Executive

        Mobica for Integrated Industries

        Address:

        (1)    3rd Industrial Zone, 6th of October City, Giza, Egypt  
        (2)    KM28 Cairo-Alex Desert Rd., Abu Rawash, Giza, Egypt  

        Mobile: (+20) 1066653810  
        Hotline: 16992  
        Email: mai.mohamed@mobica.net  
        Website: www.mobica.net  
        """
def evaluate_offers_with_groq(client,replies: List[str]) -> str:
    prompt = """
I have three offers and need to select the best one based on three factors: price, transit time, and detention days (also referred to as free demurrage). 

### Selection Criteria:
1. Detention Days (Free Demurrage):
   - The offer must have exactly 21 detention days to be valid.
   - If an offer has more than 21 detention days, it is INVALID and should be excluded from the final selection.
   - If an offer has less than 21 detention days, it is NOT PREFERABLE but still considered with a low weight in the comparison.
   
2. Transit Time (Shipping Duration):
   - The offer with the shortest total transit time should be preferred only among valid offers.
   - Ensure transit time is correctly extracted in terms of days.

3. Price Calculation (Total Cost Comparison):
   -* Strictly Calculate pricing separately for 40’HC and 20’ST containers IMO and non-IMO also Strictly MUST be separated.*
   - Each container type MUST have its own cost, Strictly MUST ADD  additional fees on each type.
   - *Do not mix 40’HC and 20’ST calculations together*—compare 40’HC offers only with other 40’HC offers and 20’ST offers only with other 20’ST offers.
   - Among valid offers, the offer with the lowest total price should be preferred.

### Output Format:
- Best Offer: [Offer Name] (If both are invalid, return "None").
- Offer Chosen Content: Strictly print the full content of the chosen offer.
- Price Comparison: The lowest total price is [X] from [Offer Name] (only among valid offers).
- Transit Time Comparison: The shortest transit time is [X days] from [Offer Name] (only among valid offers).
- Detention Days Analysis: 
  - If an offer has More than 21 detention days, explicitly state it is **INVALID and ignored.
- Final Decision Explanation: Clearly explain why the best offer was selected, ensuring proper calculations for price, transit time, and detention days. If no valid offers exist, state that no selection is possible.
"""

    for i, reply in enumerate(replies):
        prompt += f"\nOffer {i+1}:\n{reply}\n"

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", 
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"
