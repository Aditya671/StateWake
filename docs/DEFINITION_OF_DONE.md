# StateWake Definition of Done

A change is **Done** only when all applicable conditions are satisfied:

- [ ] The requirement and acceptance criteria are explicit.
- [ ] Existing/historical implementations were checked before new implementation work.
- [ ] The active architecture and product boundary remain coherent.
- [ ] Public API and compatibility impact were reviewed.
- [ ] Source follows project formatting, Ruff, PEP 8, PEP 257, and strict typing requirements.
- [ ] No diagnostic suppression was introduced to hide a defect.
- [ ] Regression tests cover the changed invariant and affected behavior.
- [ ] Platform-specific behavior is verified where applicable.
- [ ] Runtime data and generated artifacts are outside the release source tree.
- [ ] Documentation and examples match the implementation.
- [ ] Security/privacy implications were reviewed.
- [ ] Applicable quality gates pass.
- [ ] Any unavailable verification capability is explicitly recorded.
- [ ] The resulting artifact is independently verified before canonical promotion.

A release is additionally subject to the release protocol and human publication approval.
