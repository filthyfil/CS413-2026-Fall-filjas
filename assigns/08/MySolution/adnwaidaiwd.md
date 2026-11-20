

I asked AI to create the eight queens solution using CPS. Honestly, the implementation is very hard to follow (that is, CPS style) compared to a python implementation.

I think CPS and lazy evaluation complement each other very well. You compute what you want, and leave a continuation for further work, if necessary. For iterative problem solver, I think this is a good way to approach the problem, to remain lazy, and complete as little repetitive work as possible.

AI wanted to write the http server manually, I said to try again using flask, and to reuse assign07 as needed. I read the code, and tried to understand and ensure laziness and that CPS is really happening and not faked.

I reviewed the animation elements by looking looking to make sure it looks good.

Finally, confirm against the real solution since soln order is deterministic, and should be the same.
