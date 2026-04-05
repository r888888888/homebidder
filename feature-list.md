# TODO

- Assuming the DBI permit search works, let's cache it in the database. Use a 24 hour expiry.
- Create a page with a list of previously persisted analyses
- Code review of backend
- Code review of frontend
- Add an option to delete analysis from database
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

# DONE

- For fixer properties, add a Fixer vs Turn-key comparison card. What would it cost in renovations to modernize this fixer versus buying a turn-key equivalent. Use the LLM to figure out market rates for construction costs. Use teh base recommended offer price.
- Remove Prop 13 tax impact information
- Eliminate presentation specific frontend tests
- Alert on tenant occupied
- Evaluate how LLM analysis of description might affect fair value
- Factor in noise pollution and smog risk
- Resolve the "sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) table analyses has no column named risk_level" error in the backend
