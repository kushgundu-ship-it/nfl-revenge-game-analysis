"""Chart encodings only; values come from existing views and saved Stage 4 tables."""
import altair as alt
import pandas as pd

from dashboard.data import available_efficiency, require_finite

TEAL = '#0B5D3B'
SLATE = '#6F8174'
ORANGE = '#A5812C'
GROUPS = {'revenge':'Revenge','non_revenge':'Non-revenge'}
GROUP_SCALE = alt.Scale(domain=['Revenge','Non-revenge'],range=[TEAL,ORANGE])


def inline_spec(chart):
    """Keep small chart datasets inline, avoiding named Arrow dataset update races.

    The pinned Streamlit frontend can lose named datasets when switching layered
    charts. These display datasets are small; inline Vega-Lite values keep each
    rendered specification self-contained without changing any metric.
    """
    with alt.data_transformers.enable('default',consolidate_datasets=False):
        return chart.to_dict()


def finish(chart,height=300):
    return chart.properties(height=height,background='#F8F3E9').configure_view(stroke=None).configure_axis(
        labelFontSize=12,titleFontSize=12,labelColor='#385044',titleColor='#18352B',
        gridColor='#E1E2D5',domain=False,tickColor='#C3CCBD',titlePadding=12,
        labelFont='Arial',titleFont='Arial',tickCount=6
    ).configure_legend(labelFontSize=12,titleFontSize=12,labelColor='#18352B',orient='top',title=None,
                       labelLimit=220,symbolOpacity=1)


def zero_line():
    return alt.Chart(pd.DataFrame({'zero':[0]})).mark_rule(color='#738173',strokeDash=[4,4]).encode(x='zero:Q')


def interval(inference):
    frame = inference.loc[inference.effect=='equal_player_mean'].copy()
    require_finite(frame,['estimate','ci_low','ci_high'])
    frame['label'] = 'Equal-player mean'
    extent = max(abs(float(frame.ci_low.iloc[0])),abs(float(frame.ci_high.iloc[0])))*1.35
    base = alt.Chart(frame).encode(y=alt.Y('label:N',axis=None))
    whisker = base.mark_rule(color=TEAL,strokeWidth=4).encode(
        x=alt.X('ci_low:Q',title='Revenge − non-revenge mean residual (PPR)',scale=alt.Scale(domain=[-extent,extent])),
        x2='ci_high:Q',tooltip=[alt.Tooltip('ci_low:Q',format='.3f'),alt.Tooltip('ci_high:Q',format='.3f')])
    point = base.mark_point(color=TEAL,size=140,filled=True).encode(
        x='estimate:Q',tooltip=[alt.Tooltip('estimate:Q',title='Estimate',format='+.3f')])
    caps = base.transform_fold(['ci_low','ci_high'],as_=['bound','value']).mark_tick(
        color=TEAL,thickness=2,size=22).encode(x='value:Q')
    return finish(zero_line()+whisker+caps+point,115)


def distribution(frame):
    require_finite(frame,['bin_start','bin_end','percentage','games'])
    data = frame.assign(group=frame.game_group.map(GROUPS))
    chart = alt.Chart(data).mark_bar(opacity=.58,orient='vertical').encode(
        x=alt.X('bin_start:Q',title='Performance residual (PPR)'),x2='bin_end:Q',
        y=alt.Y('percentage:Q',title='Share of each group (%)',stack=None,scale=alt.Scale(domainMin=0)),
        color=alt.Color('group:N',scale=GROUP_SCALE),
        tooltip=['group:N',alt.Tooltip('bin_start:Q',title='From PPR'),
                 alt.Tooltip('bin_end:Q',title='To PPR (exclusive)'),
                 alt.Tooltip('percentage:Q',format='.2f',title='% of group'),'games:Q'])
    return finish(chart+zero_line(),295)


def group_bars(frame,category,value='mean_residual',axis_title='Mean residual (PPR)',order=None):
    require_finite(frame,[value])
    data = frame.assign(group=frame.game_group.map(GROUPS))
    present = [group for group in GROUPS.values() if group in set(data.group)]
    group_scale = alt.Scale(domain=present,range=[TEAL if group=='Revenge' else ORANGE for group in present])
    chart = alt.Chart(data).mark_bar(cornerRadiusEnd=3).encode(
        x=alt.X(f'{value}:Q',title=axis_title,axis=alt.Axis(tickCount=6)),
        y=alt.Y(f'{category}:N',title=None,sort=order or 'ascending',axis=alt.Axis(labelLimit=260)),
        yOffset='group:N',color=alt.Color('group:N',scale=group_scale),
        tooltip=[f'{category}:N','group:N',alt.Tooltip(f'{value}:Q',format='+.3f')])
    return finish(chart+zero_line(),max(160,65*data[category].nunique()))


def metric_difference(frame,axis_title):
    data,missing = available_efficiency(frame)
    chart = alt.Chart(data).mark_bar(color=TEAL,cornerRadiusEnd=3).encode(
        x=alt.X('mean_residual_difference:Q',title=axis_title),
        y=alt.Y('position:N',title=None,sort=['QB','RB','WR','TE']),
        tooltip=['position:N',alt.Tooltip('mean_residual_difference:Q',format='+.4f',title='Residual difference'),
                 alt.Tooltip('revenge_n:Q',title='Revenge n'),alt.Tooltip('non_revenge_n:Q',title='Non-revenge n')])
    return finish(chart+zero_line(),230),missing


def sensitivity(frame):
    columns=['equal_player_mean_difference','pooled_mean_difference','pooled_median_difference']
    require_finite(frame,columns)
    labels={'equal_player_mean_difference':'Equal-player mean','pooled_mean_difference':'Pooled mean',
            'pooled_median_difference':'Pooled median'}
    data = frame.melt(id_vars=['variant'],value_vars=columns,var_name='estimand',value_name='value')
    data['estimand'] = data.estimand.map(labels)
    data['variant'] = data.variant.map({'raw':'Raw','trimmed_1_99':'Trimmed 1%','winsorized_1_99':'Winsorized 1%'})
    chart = alt.Chart(data).mark_point(filled=True,size=105).encode(
        x=alt.X('value:Q',title='Revenge − non-revenge residual difference (PPR)'),
        y=alt.Y('variant:N',title=None,sort=['Raw','Trimmed 1%','Winsorized 1%']),
        color=alt.Color('estimand:N',scale=alt.Scale(domain=list(labels.values()),range=[TEAL,SLATE,ORANGE])),
        shape=alt.Shape('estimand:N',legend=None),tooltip=['variant:N','estimand:N',alt.Tooltip('value:Q',format='+.3f')])
    return finish(chart+zero_line(),230)


def baseline(support,game):
    require_finite(support,['prior_ppr_points'])
    data = pd.DataFrame({'appearance':pd.to_datetime(support.prior_game_date).dt.strftime('%Y-%m-%d'),
                         'ppr':support.prior_ppr_points,'kind':'Prior appearance'})
    data = pd.concat([data,pd.DataFrame([{'appearance':'Selected game','ppr':game.actual_ppr_points,
                                        'kind':'Selected game'}])],ignore_index=True)
    bars = alt.Chart(data).mark_bar(cornerRadiusTopLeft=3,cornerRadiusTopRight=3).encode(
        x=alt.X('appearance:N',title=None,sort=list(data.appearance),axis=alt.Axis(labelAngle=-30)),
        y=alt.Y('ppr:Q',title='PPR points'),
        color=alt.Color('kind:N',scale=alt.Scale(domain=['Prior appearance','Selected game'],range=[SLATE,ORANGE])),
        tooltip=['appearance:N',alt.Tooltip('ppr:Q',format='.2f')])
    rule = alt.Chart(pd.DataFrame({'expected':[game.expected_ppr_points]})).mark_rule(
        color=TEAL,strokeDash=[6,4],strokeWidth=2).encode(y='expected:Q',tooltip=[alt.Tooltip('expected:Q',format='.3f')])
    return finish(bars+rule,245)
