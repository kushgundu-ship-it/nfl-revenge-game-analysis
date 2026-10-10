"""Run from the repository root: python -m streamlit run dashboard/app.py"""
from pathlib import Path
import base64
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import pandas as pd
import streamlit as st

from dashboard import charts
from dashboard.data import DataIssue, POSITIONS, Repository, headline, load_bundle, signed

st.set_page_config(page_title='The Revenge Game | NFL research',page_icon='🏈',layout='wide')
st.markdown(f"<style>{(ROOT/'dashboard/style.css').read_text()}</style>",unsafe_allow_html=True)
REPOSITORY = Repository()


@st.cache_data(show_spinner=False)
def cached_bundle(signature):
    return load_bundle(REPOSITORY)


@st.cache_data(show_spinner=False)
def cached_query(name,parameters,signature):
    return REPOSITORY.query(name,list(parameters))


def query(name,*parameters):
    return cached_query(name,parameters,REPOSITORY.signature())


def chart(value):
    st.vega_lite_chart(spec=charts.inline_spec(value),width='stretch',theme=None)


def table(frame,rename=None,decimals=3):
    display = frame.rename(columns=rename or {}).copy()
    if 'Group' in display:
        display['Group'] = display['Group'].replace(charts.GROUPS)
    if 'Analysis' in display:
        display['Analysis'] = display['Analysis'].replace(
            {'raw':'Raw','trimmed_1_99':'Trimmed 1%','winsorized_1_99':'Winsorized 1%'})
    st.dataframe(display.style.format(precision=decimals,na_rep='Unavailable'),
                 hide_index=True,width='stretch')
    st.markdown('<p class="table-hint">Swipe the table horizontally to see all columns.</p>',unsafe_allow_html=True)


def intro(section,title,description):
    st.markdown(f'<div class="eyebrow">NFL / {section}</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="lead">{description}</div>',unsafe_allow_html=True)


def overview(bundle):
    tables = bundle['tables']
    inference = tables['inference']
    primary = inference.set_index('effect').loc['equal_player_mean']
    copy = headline(inference)
    stadium = base64.b64encode((ROOT/'dashboard/assets/editorial-stadium.png').read_bytes()).decode('ascii')
    st.markdown(f'''<section class="editorial-hero" aria-label="Research introduction">
<div class="hero-copy"><div class="eyebrow">NFL / The evidence</div>
<h1>Is the revenge game <em>real?</em></h1>
<p class="lead">Do NFL players outperform their recent baseline when facing a former team?</p>
<p class="hero-note">Comparing players against their old teams with those same players in other games.</p></div>
<figure><img src="data:image/png;base64,{stadium}" alt="An empty, team-neutral football stadium in warm afternoon light">
<figcaption>Original AI-generated stadium image · No team affiliation</figcaption></figure>
</section>''',unsafe_allow_html=True)
    st.caption(f"{int(primary.players):,} players · {int(primary.revenge_n):,} revenge performances · "
               f"{int(primary.non_revenge_n):,} non-revenge performances · Same-player comparison")
    columns = st.columns([1,1.3,1])
    columns[0].metric('Primary equal-player effect',copy['estimate'])
    columns[1].metric('95% player-cluster bootstrap CI',copy['interval'])
    columns[2].metric('Two-sided sign-flip p-value',copy['p_value'])
    st.markdown(f'<div class="finding"><strong>{copy["conclusion"]}</strong><br>'
                'The estimate is close to zero, and the interval permits modest effects in either direction. '
                'That is not proof of no effect, and it is not a causal finding.</div>',unsafe_allow_html=True)
    chart(charts.interval(inference))
    st.caption(f"Positive values favor revenge games. Interval from {int(primary.bootstrap_iterations):,} "
               f"whole-player bootstrap draws (seed {int(primary.bootstrap_seed)}). "
               'The p-value tests the primary equal-player mean only.')
    with st.expander('What counts as a revenge game and a baseline?'):
        st.markdown('A **former team** is the current opponent for which the player recorded **at least four earlier appearances**. '
                    'A revenge game is a meeting with that qualifying franchise; this label says nothing about motivation.\n\n'
                    '**Expected PPR** is the mean of the previous **eight appearances**, using four to seven when only those are available. '
                    'The current game and all future games are excluded. Histories continue across seasons and transfers.\n\n'
                    '**Performance residual (uplift) = actual PPR − expected PPR.** '
                    'PPR means fantasy points with one point per reception. Both groups use the same definitions.')
    st.subheader('The distributions overlap')
    position = st.selectbox('Distribution position',('All positions',)+POSITIONS,key='distribution_position')
    distribution = query('histogram',position,position)
    if distribution.empty:
        st.info('No eligible performances for this selection.')
    else:
        chart(charts.distribution(distribution))
        counts = distribution.groupby('game_group').games.sum()
        st.caption(f"{int(counts.get('revenge',0)):,} revenge / {int(counts.get('non_revenge',0)):,} non-revenge. "
                   'Each distribution sums to 100%; all residuals are shown in 2-PPR bins. '
                   'This filter does not change the full-cohort inference above.')
    st.subheader('Three summaries, different questions')
    explanation = {
        'equal_player_mean':('Primary · equal-player mean','Each player contributes one difference between their two group means.'),
        'pooled_mean':('Pooled · game-weighted mean','Games have equal weight within each group; players with more games contribute more.'),
        'equal_player_median':('Secondary · player medians','The mean of within-player median differences, not the pooled median.')}
    for effect,(label,description) in explanation.items():
        row = inference.set_index('effect').loc[effect]
        st.markdown(f"**{label}: {signed(row.estimate)} PPR** · 95% CI {signed(row.ci_low)} to {signed(row.ci_high)}. {description}")
    st.info('The positive secondary median contrast is exploratory. Sparse revenge histories, unequal group sizes, '
            'and several examined outcomes limit its interpretation. It does not overturn the primary mean result.')
    st.caption('Statistical significance and football importance are different questions. '
               'A small p-value would not make a tiny PPR difference useful. No equivalence test was performed.')
    st.download_button('Download saved inference',data=(REPOSITORY.tables/'stage4_inference.csv').read_bytes(),
                       file_name='stage4_inference.csv',mime='text/csv')


METRICS = {
    'opportunities':('Opportunities','Opportunities per game'),
    'pass_attempts':('Pass attempts','Attempts per game'),
    'carries':('Carries','Carries per game'),
    'targets':('Targets','Targets per game'),
    'receptions':('Receptions','Receptions per game'),
    'passing_yards_per_attempt':('Passing yards / attempt','Yards per pass attempt'),
    'rushing_yards_per_carry':('Rushing yards / carry','Yards per carry'),
    'receiving_yards_per_target':('Receiving yards / target','Yards per target'),
    'touchdowns_per_opportunity':('Touchdowns / opportunity','TD per opportunity')}


def patterns(bundle):
    tables = bundle['tables']
    intro('Explore the patterns','Beyond the average',
          'Descriptive comparisons help explain the data. They are not separate discoveries or causal effects.')
    view = st.radio('Explore',['Positions & reunions','Usage & efficiency','Outlier sensitivity'],horizontal=True,key='pattern_view')
    if view=='Positions & reunions':
        choices = {'Position':'position','First vs later meeting':'meeting','Home vs away':'venue',
                   'Time since former team':'departure'}
        choice = st.selectbox('Breakdown',list(choices),key='breakdown')
        frame = tables['segments'].loc[tables['segments'].breakdown==choices[choice]].copy()
        frame['segment'] = frame.segment.replace({'first':'First meeting','later':'Later meeting',
            'home':'Home','away':'Away','01_0_to_365_days':'0–365 days','02_366_to_730_days':'366–730 days',
            '03_731_to_1460_days':'731–1,460 days','04_1461_plus_days':'1,461+ days'})
        order = list(POSITIONS) if choice=='Position' else list(frame.segment.drop_duplicates())
        chart(charts.group_bars(frame,'segment',order=order))
        table(frame[['segment','game_group','games','players','mean_residual','median_residual','pct_exceeded']],
              {'segment':'Segment','game_group':'Group','games':'Games','players':'Players',
               'mean_residual':'Mean PPR residual','median_residual':'Median PPR residual','pct_exceeded':'Exceeded (%)'})
        if choice=='First vs later meeting':
            st.caption('Revenge games only. First means the first observed qualifying meeting with each former franchise. '
                       'The flag does not reset after a return stint. Player groups overlap and are not matched.')
        elif choice=='Time since former team':
            st.caption('Revenge games only. Days since the most recent recorded appearance for the former team, '
                       'not a transaction date. Fixed buckets approximate ≤1, 1–2, 2–4, and >4 years.')
        elif choice=='Home vs away':
            st.caption('Schedule-designated home/away, including neutral-site games. This is a description, not a home-field adjustment.')
        st.caption('All bars are game-weighted group summaries, not equal-player estimates. No subgroup significance tests were run.')
    elif view=='Usage & efficiency':
        a,b = st.columns([1,2])
        family = a.selectbox('Metric family',['Usage','Efficiency'],key='metric_family')
        frame = tables['usage_efficiency_differences']
        available = set(frame.loc[frame.metric_family==family.lower(),'metric'])
        metric = b.selectbox('Metric',[k for k in METRICS if k in available],format_func=lambda x:METRICS[x][0],key='usage_metric')
        selected = frame.loc[frame.metric==metric]
        plot,missing = charts.metric_difference(selected,f'Δ residual · {METRICS[metric][1]}')
        chart(plot)
        st.caption('Revenge minus non-revenge mean residual. Positive means higher relative to recent baseline. '
                   'The units differ by metric; bars are not PPR effects.')
        if not missing.empty:
            st.info('Unavailable contrast: '+', '.join(missing.position)+'. No valid revenge residuals; '
                    'undefined ratios stay missing, not zero.')
        if (selected.revenge_n.between(1,9)).any():
            st.warning('At least one position has fewer than 10 valid revenge observations. Treat that bar with particular caution.')
        detail = tables['usage_efficiency'].loc[tables['usage_efficiency'].metric==metric]
        table(detail[['position','game_group','residual_n','mean_actual_paired','mean_expected_paired','mean_residual']],
              {'position':'Position','game_group':'Group','residual_n':'Valid games','mean_actual_paired':'Actual',
               'mean_expected_paired':'Expected','mean_residual':'Residual'},decimals=4)
        with st.expander('Definitions and unavailable observations'):
            st.markdown('**QB opportunities = pass attempts + carries. RB/WR/TE opportunities = carries + targets.** '
                        'Receptions are separate and are never added again.\n\n'
                        'Efficiency baselines average valid game-level ratios inside the same previous-eight-appearance window, '
                        'requiring at least four valid historical ratios. A missing or zero denominator produces NULL; '
                        'older games never backfill the window. TD numerators are passing + rushing for QB and rushing + receiving for other positions.\n\n'
                        'Groups can contain different valid subsets. This is not a causal decomposition of PPR.')
            table(detail[['position','game_group','eligible_games','actual_n','expected_n','residual_n']],
                  {'position':'Position','game_group':'Group','eligible_games':'Eligible','actual_n':'Actual defined',
                   'expected_n':'Baseline available','residual_n':'Both available'},decimals=0)
    else:
        st.subheader('Do extreme games drive the mean?')
        chart(charts.sensitivity(tables['sensitivity_results']))
        table(tables['sensitivity_results'][['variant','equal_player_mean_difference','pooled_mean_difference',
            'pooled_median_difference','paired_players']].rename(columns={'variant':'Analysis',
            'pooled_mean_difference':'Pooled mean','pooled_median_difference':'Pooled median',
            'paired_players':'Paired players','equal_player_mean_difference':'Equal-player mean'}))
        cutoff = tables['outlier_cutoffs'].iloc[0]
        st.markdown(f"Common cutoffs across both groups: **{signed(cutoff.p01,4)} to {signed(cutoff.p99,4)} PPR**. "
                    'Trimming excludes values outside them; winsorization clips values to them. Source records are unchanged.')
        st.caption('All mean differences remain near zero. Sensitivity values are descriptive, without new tests or confidence intervals. '
                   'Trimming changes the estimand and excludes players without both surviving groups from the equal-player result.')
        with st.expander('Inspect the largest positive and negative revenge performances'):
            table(tables['extreme_revenge'][['player_display_name','game_id','team','opponent_team','performance_residual']],
                  {'player_display_name':'Player','game_id':'Game','team':'Team','opponent_team':'Former team',
                   'performance_residual':'PPR residual'})


def explorer(bundle):
    intro('Player explorer','Look up a player and a game.',
          'See what happened against a former team and how it compared with recent games. One game does not tell the whole story.')
    examples = bundle['examples']
    st.caption('Choose one of these examples, or search for a player below.')
    for column,row in zip(st.columns(4),examples.itertuples()):
        if column.button(row.player_display_name,key=f'example_{row.player_id}',width='stretch'):
            st.session_state['player_id'] = row.player_id
            st.session_state[f'game_{row.player_id}'] = row.game_id
    players = bundle['players'].set_index('player_id')
    ids = list(players.index)
    if 'player_id' not in st.session_state:
        st.session_state['player_id'] = examples.iloc[0].player_id
    player_id = st.selectbox('Player',ids,key='player_id',format_func=lambda pid:
        f"{players.loc[pid,'player_display_name']} · {players.loc[pid,'positions']} · {pid}")
    games = query('player_games',player_id)
    if games.empty:
        st.info('No eligible revenge games for this player in the saved cohort.')
        return
    st.caption(f"Stable player ID: {player_id} · {int(players.loc[player_id,'revenge_n'])} revenge / "
               f"{int(players.loc[player_id,'non_revenge_n'])} comparison performances. No player-level significance claim.")
    st.subheader('Revenge-game ledger')
    ledger = games[['game_date','team','former_team','actual_ppr_points','expected_ppr_points',
                    'performance_residual','revenge_score','first_meeting']].copy()
    ledger['game_date'] = pd.to_datetime(ledger.game_date).dt.strftime('%Y-%m-%d')
    ledger['first_meeting'] = ledger.first_meeting.map({True:'First',False:'Later'})
    table(ledger,{'game_date':'Date','team':'Team','former_team':'Former team','actual_ppr_points':'Actual PPR',
                  'expected_ppr_points':'Expected PPR','performance_residual':'Uplift','revenge_score':'Std. score',
                  'first_meeting':'Meeting'},decimals=2)
    by_game = games.set_index('game_id')
    game_id = st.selectbox('Inspect a baseline',list(by_game.index),key=f'game_{player_id}',format_func=lambda gid:
        f"{by_game.loc[gid,'game_date']:%b %d, %Y} · {by_game.loc[gid,'team']} vs {by_game.loc[gid,'former_team']} · {gid}")
    game = by_game.loc[game_id]
    columns = st.columns(3)
    columns[0].metric('Actual PPR',f'{game.actual_ppr_points:.2f}')
    columns[1].metric('Rolling expected PPR',f'{game.expected_ppr_points:.3f}')
    columns[2].metric('Uplift / residual',signed(game.performance_residual))
    if pd.isna(game.revenge_score):
        st.info('Standardized score unavailable: '+str(game.revenge_score_unavailable_reason).replace('_',' ')+'. '
                'The raw residual is still valid.')
    else:
        st.caption(f'Standardized score: {signed(game.revenge_score)} recent-history standard deviations.')
    support = query('baseline',player_id,game_id)
    st.subheader(f'The {len(support)} appearances behind this baseline')
    chart(charts.baseline(support,game))
    st.caption('Dashed green line: the stored rolling expectation. Bars are actual PPR. '
               'The selected game is excluded from its baseline; gaps and transfers do not reset the window.')
    display = support[['prior_game_date','prior_team','prior_opponent_team','prior_ppr_points','prior_game_id']].copy()
    display['prior_game_date'] = pd.to_datetime(display.prior_game_date).dt.strftime('%Y-%m-%d')
    table(display,{'prior_game_date':'Date','prior_team':'Team','prior_opponent_team':'Opponent',
                   'prior_ppr_points':'PPR','prior_game_id':'Supporting game'},decimals=2)


def methods(bundle):
    intro('Methods & limits','How the analysis works',
          'Each game is compared with earlier appearances. The statistical tests account for players appearing more than once.')
    diagram = base64.b64encode((ROOT/'docs/data_flow.svg').read_bytes()).decode('ascii')
    st.markdown(f'<div class="flow-diagram" tabindex="0" aria-label="Scrollable data-flow diagram">'
                f'<img src="data:image/svg+xml;base64,{diagram}" alt="Raw data to cleaned games, former-team history, '
                'rolling features, same-player comparisons, inference, and dashboard"></div>',unsafe_allow_html=True)
    st.markdown('<p class="table-hint">Swipe the diagram horizontally to follow the data flow.</p>',unsafe_allow_html=True)
    st.caption('All dashboard database connections are read-only. Aggregate inference is loaded from saved Stage 4 outputs.')
    st.subheader('How to read the evidence')
    st.markdown('1. **Identify former teams:** at least four strictly earlier recorded appearances for the current opponent.\n'
                '2. **Set expectations:** previous eight appearances, minimum four; no current or future game.\n'
                '3. **Compare the same players:** eligible revenge and non-revenge residuals with identical definitions.\n'
                '4. **Respect dependence:** resample whole players; the primary sign-flip test operates on one mean difference per player.')
    primary = bundle['tables']['inference'].set_index('effect').loc['equal_player_mean']
    st.caption(f"{int(primary.bootstrap_iterations):,} bootstrap draws; seed {int(primary.bootstrap_seed)}. "
               f"Sign-flip seed {int(primary.sign_flip_seed)}. Percentile confidence intervals. "
               'The sign-flip model requires independent player contrasts with sign symmetry under the null.')
    st.subheader('What this analysis cannot establish')
    st.markdown('- **No causal identification.** Facing a former team was not randomly assigned.\n'
                '- **Limited history.** Records begin in 2015 and include regular-season QB, RB, WR, and TE appearances only. '
                'Pre-2015 service, postseason, roster-only records, and other positions are absent.\n'
                '- **Dependence remains.** Player clustering handles repeated observations within players; shared teams, opponents, '
                'and NFL games can still create cross-player dependence.\n'
                '- **Confounding and selection.** Role, injuries, opponent strength, age, and transfer/cohort selection may explain patterns. '
                'Usage and venue summaries are descriptive, not statistical controls.\n'
                '- **Uncertainty is not proof of absence.** Failing to reject zero does not prove no effect. Statistical significance '
                'does not determine football importance.\n'
                '- **Exploration is not confirmation.** Position splits and the positive secondary median contrast do not overturn '
                'the primary mean result. Small and unequal subgroup samples require caution.')
    st.subheader('Validation and sources')
    checks = bundle['tables']['validation']
    st.write(f"The saved Stage 4 report passed {int((checks.severity=='ERROR').sum())} SQL error checks across Stages 1–4.")
    warnings = checks.loc[(checks.severity=='WARN') & (checks.problem_count>0)]
    table(warnings,{'stage':'Stage','check_name':'Existing raw-data warning','severity':'Severity','problem_count':'Rows'},decimals=0)
    st.caption('These raw-data warnings do not enter the cleaned analysis. Run scripts/validate_stage5.py and the test suite '
               'to check the live database, dashboard queries, and presentation contracts.')
    st.markdown('Source: [nflverse player statistics](https://nflreadr.nflverse.com/reference/load_player_stats.html) '
                'and [schedules](https://nflreadr.nflverse.com/reference/load_schedules.html). '
                'The local raw-file manifest records the exact snapshot.')
    st.caption('The detailed research report is docs/stage4_results.md in the repository. '
               'Its relative table links are intended for repository browsing, not this local app.')
    st.download_button('Download Stage 4 report',(ROOT/'docs/stage4_results.md').read_bytes(),
                       file_name='stage4_results.md',mime='text/markdown')


def main():
    with st.sidebar:
        st.markdown('<div class="eyebrow">NFL PLAYER ANALYSIS</div><div class="brand">The Revenge Game</div>',unsafe_allow_html=True)
        page = st.radio('Navigate',['Overview','Patterns','Player explorer','Methods & limits'],key='page')
        st.divider()
        st.markdown('<div class="sidebar-note">SQL · DuckDB · Python<br><br>'
                    'Compare the overall results,<br>then look up individual games.</div>',unsafe_allow_html=True)
    try:
        bundle = cached_bundle(REPOSITORY.signature())
        with st.sidebar:
            scope = bundle['scope']
            st.caption(f"{int(scope['first_season'])}–{int(scope['last_season'])} seasons · Regular season\n\nQB / RB / WR / TE")
        {'Overview':overview,'Patterns':patterns,'Player explorer':explorer,'Methods & limits':methods}[page](bundle)
        st.divider()
        st.caption('NFL Revenge Game Analysis · Local portfolio dashboard · Observational evidence, not a causal claim')
    except DataIssue as error:
        st.error(str(error))
        st.info('From the project folder, follow the README setup steps and complete Stages 1–4. '
                'The dashboard never creates, edits, or repairs analytical data automatically.')


main()
