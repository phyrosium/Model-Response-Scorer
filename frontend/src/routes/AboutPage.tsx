import { Link } from 'react-router-dom'

export default function AboutPage() {
  return (
    <div className="card prose">
      <h2>About</h2>

      <p>
        Model Response Scorer is a small evaluation harness. You write a prompt,
        generate a response from a Claude model, define a rubric of weighted
        criteria, and then score that response twice: once by hand, and once by
        an LLM acting as a judge. The two sets of scores sit side by side with a
        difference on each criterion.
      </p>

      <p>
        The comparison is the point. Using a model to grade model output is now
        a common way to evaluate at a scale humans cannot match, but it is only
        worth doing if the judge broadly agrees with a careful human on cases
        where you already know the answer. This tool exists to make that
        agreement, or the lack of it, visible on your own prompts and your own
        rubric rather than on a benchmark. So the judge is never shown the
        manual scores. Anchoring it to a number it was just handed would turn
        the comparison into a test of whether the model can copy.
      </p>

      <h3>The judge is not deterministic</h3>

      <p>
        The most interesting result so far came from re-running the judge on an
        unchanged response with an unchanged rubric. It did not reproduce its
        own answer. On one response it scored Tone 4 on the first run and 5 on
        the second, and rewrote every rationale in between. Nothing about the
        input had changed.
      </p>

      <p>
        This matters for how the numbers here should be read. A single automated
        score is a sample, not a measurement, and a difference of one point
        against a human may be judge variance rather than genuine disagreement.
        For anything load-bearing, several runs and the spread between them
        would be more honest than one number. The current schema stores exactly
        one automated score per criterion, so capturing that spread would need a
        change to the data model rather than just to the interface.
      </p>

      <div className="divider" />

      <p className="small muted">
        Built with React and TypeScript, FastAPI, and Postgres, orchestrated with
        Docker Compose. Generation and judging both call the Anthropic API
        directly. New here? The <Link to="/how-to">How-to</Link> page walks
        through the workflow in order.
      </p>
    </div>
  )
}
