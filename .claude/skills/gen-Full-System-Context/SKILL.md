Step 1:
You will build a complete code-backed inventory of the system from the source code. This step
focuses on discovery and completeness. Do not remove uncertain or legacy findings unless they
are clearly irrelevant
Tasks:
1. Recursively scan the full source code tree
2. Identify the main system components, microservices, and modules
3. Identify likely external systems from the code, configuration if available
4. Identiff all candidate inbound and outbound interfaces
Deliverables:
1. Application Overview
Suggested naming: "Application Overview.html"
lnclude the following:
- A description of the system's role and functionality
- Technical stack summary
- List of identified microservices, system components, or modules, with description
- List of identified external systems, with description
- List of identified downstream channels, with descriptiorl
2. Interface Inventory
Suggested naming: "inventory.csv"
Create an inventory table with the following fields
- Interface Index
- API Name
- Direction
- Inbound or Outbound
- System Boundary
- Internal
- Extemal
- Downstream
- Calling System / Target System
- Calling System for inbound
- Target System for outbound
- Protocol(s)
- Microservice Called / Microservice Caller
- Microservice Called for inbound
- Microservice Caller for outbound
s\
Using the application overview and interface inventory from the previous step, reconstrrrct the key
business processes supported by the system
Tasks:
1. Identify and group related interfaces and system behaviors into meaningful business processes
2. Reconstruct the likely end-to-end journey for each business process
3. Identify which system components, external systems, and interfaces are involved
Deliverables:
The information from the two deliverables below will be r"rsed to enrich the existing file
"Application Overview.html "
1. Business Process Summary
For each key business process, include:
- Business Process Index
- Business Process Name
- lmpofiance
- Suggested levels: High, Medium, Low
- Business Objective
- Brief description of the business purpose and requirement of the process
- Step-Based Description
- Describe the end-to-end joumey of the process in sequential steps
2. Business Process Flows
For each key business process, provide a Mermaid flow diagram. Each flow should include
- The main steps of the process from start to finish
- Clear labels for decision branches.
- Enough detail to support visual understanding without becoming too technical
Step 3:
Using the completed application overview and business process analysis, generate the following
documentations:
1. System Architecture
Suggested naming: "System Architecture.html"
Create a visual architecture page with the following sections
- Inbound Systems
Step 2:
- Core Components / Microservices
- Outbound Systems
- Dor.vnstream Channels
F'or each system and microservice, show
- Systern or component name
- Shorl metadata if r-rsefirl
At the bottom of the page, include simple sumlrlary tables for:
- lnbound systems
- Core components / microservices
- Outbound systems
- Downstream channels
Each table should include
- Name
- Short description
2. Inbound Interface Analysis
Suggested naming : " Inbound Interface Analysis.html "
Include all code-backed inbound interfaces, including legacy ones. Organize the page as
- External lnbound lnterfaces
- Intemal lnbound Interfaces
Internal interfaces can be collapsible if there are many records. For each interface, show
- API Name
- Usage Status badge
- System Boundary
- Calling System
- Protocol(s)
- Microservice Called
- API Path, if available
- Request Parameters
- Response Parameters
- Interface Functionality
3. Outbound Interface Analysis
Suggested naming : " Outbound Interface Analysis. html "
Inclr-rde all code-backed outbound interfaces, inclLrding iegacy ones. Organize the page as
- External Or"rtbound Interfaces
- Internal Outbound Interfaces
Internal interfaces can be collapsible if there are many records. For each interface, show:
- API Name
- Usage Status badge
- System Boundary
- Microservice Caller
- Protocol(s)
- Target System
- API Path, if available
- Request Parameters
- Response Parameters
- Interface Functionality
Step 4:
Using the completed application overview, business process analysis and the interface analysis,
generate the following Service Flow lists:
1. Inbound Service Flow List
Suggested naming: "Inbound Service Flow List.xlsx"
Create an Excel table for inbound interfaces with the following columns:
- Idx
- API Name
- Usage Status
- lnterface Functionality
- Systern Boundary
- Calling Systern
- Protocol(s)
- Microservice Called
- API Path
- Service Scenario
- Service Description
2. Outbound Seruice Flow List
Suggested naming: "Outbound Service Flow List.xlsx"
Create an Excel table for outbound interfaces with the following colutmns
- Idx
- API Name
- Usage Status
- API Category
- lnterface Functionality
- Systern Boundary
- Microservice Caller
-
- Protocol(s)
- Target System
- API Path
- Service Scenario
- Seryice Description
Step 5:
Using the generated HTML deliverables and the Service Flow Lists, create a slide outline that will
be used to design the slides for presenting the deliverables to the stakeholders
Create:
- slide outline.md
lnclude:
- Approximately 10-i2 slides, can be over the count if necessary but prioritize the most essentiai
10 cards for me
- Ifthere are any abbreviations, add a descriptive reference below as "glossary" to aliow audience
to know what that is, if needed
- The presentation flow will:
1. Starl from a descriptive system positioning, with reference tech stack (1 slide, 1eft is the
description and right is the reference tech stack)
2. Highlight the key functionalities of the system (1 slide)
3. Talk abor"rt the key business processes of high priority and above
- Don't include too much details per slide but add the details as presenter note in the outline