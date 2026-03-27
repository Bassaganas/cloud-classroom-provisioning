---
name: implement plan
description: Once the implementation plan is created using the "create plan" prompt, use this prompt to execute the plan step by step, including writing code, creating tests, and fixing any issues that arise. Follow the plan closely and report on progress at each stage.
---
```

Follow all rules in .github/instructions/*
Execute the implementation plan created for the following features and requirements including frontend components, backend API changes, and testing strategy:

[Your specific request here]

Make reasonable assumptions for unclear points and list them at the end.
Do not ask questions mid-task; proceed through test implementation → test execution → implementation → test execution → fixes → summary.

Finally implement all e2e tests in Playwright for the new functionallity, and ensure they are passing together with the rest of test cases. If any tests fail, fix the implementation until all tests pass.

Once all tests are passing and the implementation is complete, provide a summary of the changes made, including any assumptions that were necessary to complete the task and a test pass/fail summary.
```
