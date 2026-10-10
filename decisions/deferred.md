# What is deliberately not done yet

A thing left undone with no trigger is a thing forgotten. Each row names what
would make it worth doing, so the question comes back on its own rather than
depending on someone remembering it. Nothing enforces a trigger; the list is
read whenever a decision record is written and when a phase ends.

| Not done | The trigger | Why not now |
|---|---|---|
| A coverage threshold in CI | Two months of measured coverage to set it below | A number picked before there is data is a guess with a gate on it |
| A code of conduct and issue templates | A second contributor, or the first outside issue | Boilerplate answering questions nobody has asked |
| A release workflow and publishing | The first release someone outside will install | A published name is claimed and a published version cannot be reused |
| `CODEOWNERS` | A second person who reviews | It would name one person as the owner of everything |
| `pre-commit` as a requirement rather than an option | A second contributor | The gates run in CI, and a hook one person installs is a hook one person maintains |
| A `tour` tool for guided tours | Roy has driven with `where_am_i` and `whats_around` and asks for a tour | A tour builds on readings that arrive reliably, which is not yet tried in a car |
| The phone sending readings here directly | A drive where the voice bridge is not running | The bridge already receives every reading; one sender is simpler |
| Authentication on the HTTP routes | Listening anywhere but 127.0.0.1 | Only this machine can reach it |
| Making the repository public | Roy decides | It holds no data, but publishing cannot be undone |
