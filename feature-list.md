# TODO

- Incorporate React Query for API calls
- Assuming the DBI permit search works, let's cache it in the database. Use a 24 hour expiry.
- Code review of backend
- Code review of frontend
- Move feature flags into database, add admin portal
- Support inspection reports
- Support pest inspection reports
- Support disclosures
- Support education locality
- Add opportunity cost versus renting
- Review other potential factors for affecting retail price
- Compact final analysis prompt
- Add StreetView link
- Organize page into tabs
- Support school quality
- Factor in seasonality of sales
- Why does "88 Hoff St #104, San Francisco, CA 94110" not find the correct unit?
- Why does "88 Hoff St Apt 104, San Francisco, CA 94110" produce a low offer recc that's higher than the high offer recc?
- Readd rent estimation tools

# DONE

- Clicking on description should expand to full text
- Can we persist the fixer analysis card in the database
- Analyzing a property seems to insert it into the database twice
- Add renovation estimate for siding replacement
- Remove rentcast integration entirely
- fix sensitivity of fixer/renovated badges
- Brainstorm better methods for estimating renovation costs
  - Make each line item in renovation toggleable to adjust total renovation estimate
- Add an option to delete analysis from database
- Create a page with a list of previously persisted analyses
- For fixer properties, add a Fixer vs Turn-key comparison card. What would it cost in renovations to modernize this fixer versus buying a turn-key equivalent. Use the LLM to figure out market rates for construction costs. Use teh base recommended offer price.
- Remove Prop 13 tax impact information
- Eliminate presentation specific frontend tests
- Alert on tenant occupied
- Evaluate how LLM analysis of description might affect fair value
- Factor in noise pollution and smog risk
- Resolve the "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table analyses has no column named risk_level" error in the backend
- Handle backend error: "Anthropic bad request (400): Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase credits.'}, 'request_id': 'req_011CZoKt4KB8yaQZQg6uRaJw'}"
