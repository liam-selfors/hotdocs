# R-LOOP-003

**R-LOOP-003** — The first attempt's feedback MUST be the caller's
  `retry_feedback`, sorted and de-duplicated. Each later attempt's
  feedback MUST be the sorted union of the previous attempt's feedback
  and its `failed_requirements`: the `covers` value of every criterion
  in its verification report whose `result` is `fail` and whose
  `failure_origin` is not `"test"`. A surface or generation failure adds
  no ids. Nothing but those requirement ids is ever passed as feedback.
