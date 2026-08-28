import { Link } from 'react-router-dom'

export default function HowToPage() {
  return (
    <div className="card prose">
      <h2>How to use this tool</h2>
      <p className="muted">
        The five steps below run in order. Each one depends on the one before
        it, so the first time through it is worth following them start to
        finish.
      </p>

      <ol className="steps">
        <li>
          <h3>Add a prompt</h3>
          <p>
            On the <Link to="/prompts">Prompts</Link> page, write the prompt you
            want to evaluate. A title is optional and only there to make it
            easier to find later.
          </p>
        </li>

        <li>
          <h3>Generate a response</h3>
          <p>
            Still on the Prompts page, pick a model and press{' '}
            <em>Generate response</em>. The call is synchronous, so the page
            waits until the model replies. Generate more than once, or against
            different models, if you want several responses to compare. Press{' '}
            <em>Show responses</em> to read what came back.
          </p>
        </li>

        <li>
          <h3>Build or pick a rubric</h3>
          <p>
            On the <Link to="/rubrics">Rubrics</Link> page, create a rubric with
            one criterion per thing you want to judge. Each criterion carries its
            own maximum, so a single rubric can mix a 0 to 5 scale with a 0 to 3
            one, and its own weight, which controls how much it counts toward
            the total. A weight of 0 means the criterion is scored but left out
            of the total.
          </p>
          <p className="small muted">
            Criteria appear when scoring in the order you add them here. Rubrics
            are reusable and independent of any one prompt, so an existing one
            is usually the better starting point.
          </p>
        </li>

        <li>
          <h3>Score it yourself</h3>
          <p>
            On the <Link to="/scoring">Scoring</Link> page, choose the prompt,
            then one of its responses, then a rubric. Give each criterion a
            score and, if it helps, a short rationale. A running weighted total
            appears as you go.
          </p>
          <p className="small muted">
            Scores save one criterion at a time and can be changed afterwards.
            Re-submitting a criterion replaces your earlier score rather than
            adding a second one.
          </p>
        </li>

        <li>
          <h3>Compare against the judge</h3>
          <p>
            On the <Link to="/comparison">Comparison</Link> page, pick the same
            response and rubric, then press{' '}
            <em>Auto-score with Claude</em>. The judge scores every criterion
            independently and its results appear beside yours, with a per
            criterion difference, both sets of reasoning, and a summary showing
            how often the two of you agreed.
          </p>
          <p className="small muted">
            The judge is never shown your scores, so the two sides stay
            independent. You can score manually before or after running it; only
            criteria that have both a manual and an automated score produce a
            difference.
          </p>
        </li>
      </ol>

      <div className="divider" />
      <p className="small muted">
        Nothing here is destructive. Re-running the judge replaces its previous
        answer rather than piling up duplicates, and your manual scores are
        never overwritten by it.
      </p>
    </div>
  )
}
