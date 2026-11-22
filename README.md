# Validator-AF

Validator Exercise using Python for an interview with AppsFactory.

As per the case study file provided with this challenge.
The changes up until the commit a74edab10a4ee307d07040f9cb8bb5a267f639da
Are the only ones within the "3 hours of work, with a 4-hour maximum constriction", everything pushed after that is just an attempt to try to give a little more form to how the project was supposed to work (Basically documentation that I didn't add in time).

What was I planning to do next but I was unable due to time limitations:
- Use the different .csv or .md files already generated to create a more concise report of what is going on with both versions
- Add a step to delete the unused files that remained in the output dir.
- Create unit tests with pytest so that they can be used for the CI/CD proposal, the main focus of the test would have been checking that:
    - Checking for gap excedence, risk-priority filtering and enforce non-zero exit gates on latency (based on the 150ms stated in the case study)
- As for the release decision, I'm not sure but based on the fact that for 2.5.0 the latency in the p95 is more than expected (11ms more or ~7% over). For me the answer is: Hold the release until a root-cause or posible fix is found.


## Installation
Run the following commands to install the dependencies needed for the project

- pip install -r requirements.txt


## Execution
Run the following commands to execute the tool

- python validatorTool.py
