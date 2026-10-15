#!/usr/bin/env python3
"""Audit real L2 events against an independent state model; build the simulator first."""
from pathlib import Path
import subprocess,os,sys,json,csv,importlib.util,tempfile
ROOT=Path(__file__).resolve().parents[1]; TMP=Path(tempfile.mkdtemp(prefix='irrip-audit-'))
OUT=ROOT/'results/task2/audit';OUT.mkdir(exist_ok=True)
source=(ROOT/'replacement/irrip.l2c_repl').read_text().replace('#include <cstdlib>','#include <cstdlib>\n#include <fstream>')
needle='int instruction_insert, data_hit, eviction_bias, instruction_aware;'
source=source.replace(needle,needle+r'''
std::ofstream audit(std::getenv("IRRIP_AUDIT_FILE"));
unsigned audit_events = 0;
unsigned audit_victim(unsigned set, const BLOCK *blocks, unsigned selected,
                      const unsigned *before) {
    if (audit_events++ < 200000) {
        audit << "V " << set << " " << selected;
        for (unsigned w=0;w<L2C_WAY;++w)
            audit << " " << unsigned(blocks[w].valid) << " " << unsigned(blocks[w].instruction)
                  << " " << before[w] << " " << unsigned(rrpv[set][w]);
        audit << '\n';
    }
    return selected;
}
''')
needle='    for (unsigned way = 0; way < L2C_WAY; ++way)\n        if (!current_set[way].valid) return way;'
source=source.replace(needle,'''    unsigned before[L2C_WAY];
    for (unsigned w=0;w<L2C_WAY;++w) before[w]=rrpv[set][w];
    for (unsigned way = 0; way < L2C_WAY; ++way)
        if (!current_set[way].valid) return audit_victim(set, current_set, way, before);''')
source=source.replace('return data;','return audit_victim(set, current_set, data, before);').replace('return first_distant;','return audit_victim(set, current_set, first_distant, before);')
needle='    rrpv[set][way] = hit ? (instruction ? 0 : data_hit) :'
source=source.replace(needle,'    unsigned before = rrpv[set][way];\n'+needle)
needle='        (instruction ? instruction_insert : 2);'
source=source.replace(needle,needle+r'''
    if (audit_events++ < 200000)
        audit << "U " << set << " " << way << " " << type << " " << unsigned(hit)
              << " " << unsigned(isInstruction) << " " << unsigned(block[set][way].instruction)
              << " " << before << " " << unsigned(rrpv[set][way]) << '\n';
''')
(TMP/'audit.cc').write_text(source)
subprocess.run(['clang++','-std=c++11','-O3','-Iinc','-c',str(TMP/'audit.cc'),'-o',str(TMP/'audit.o')],check=True)
objects=[str(p) for p in (ROOT/'obj').rglob('*.o') if p!=ROOT/'obj/replacement/l2c_replacement.o']
subprocess.run(['clang++',*objects,str(TMP/'audit.o'),'-o',str(TMP/'audit')],check=True)
spec=importlib.util.spec_from_file_location('sweep',ROOT/'scripts/sweep_task2.py');sweep=importlib.util.module_from_spec(spec);spec.loader.exec_module(sweep)
rows=[];examples=[]
for trace in sorted((ROOT/'traces').glob('*.gz')):
 for cfg in sweep.configurations():
  if cfg['policy']!='irrip':continue
  env={**os.environ,'IRRIP_AUDIT_FILE':str(TMP/'events.log')}
  for key,var in [('insert','INSERT'),('data_hit','DATA_HIT'),('aware','AWARE'),('bias','BIAS')]:env['IRRIP_'+var]=str(cfg[key])
  with (TMP/'simulation.log').open('w') as f:
   subprocess.run([str(TMP/'audit'),'-warmup_instructions','250000','-simulation_instructions','250000','-traces',trace.name],cwd=trace.parent,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
  sweep.metrics((TMP/'simulation.log').read_text(),250000)
  # Independent state model: direct max-distance aging, no production victim loop.
  state=[[[False,False,3] for _ in range(8)] for _ in range(1024)]
  stats=dict(trace=trace.name,config=cfg['name'],events=0,fills=0,hits=0,evictions=0,aged=0,instruction_victims=0,data_victims=0,mixed_hits=0,protected_instruction=0)
  sample_counts={}
  for line in (TMP/'events.log').read_text().splitlines():
   parts=line.split();nums=list(map(int,parts[1:]));stats['events']+=1
   if parts[0]=='U':
    set_,way,type_,hit,incoming,resident,before,after=nums
    valid,kind,age=state[set_][way]
    assert before==age,(cfg,line,'RRPV before',age)
    is_code=bool(incoming and type_ in (0,2))
    if hit:
     assert valid,(cfg,line,'hit invalid')
     stats['hits']+=1
     if is_code and not kind:stats['mixed_hits']+=1
     kind=kind or is_code
     assert resident==kind,(cfg,line,'sticky classification',kind)
     expected=0 if kind else cfg['data_hit']
    else:
     stats['fills']+=1
     assert resident==kind,(cfg,line,'victim classification',kind)
     kind=is_code
     expected=cfg['insert'] if kind else 2
    assert after==expected,(cfg,line,'RRPV after',expected)
    state[set_][way]=[True,kind,expected]
   else:
    set_,selected=nums[:2];reported=[nums[2+i*4:6+i*4] for i in range(8)]
    old=[x[:] for x in state[set_]]
    assert [x[:3] for x in reported]==old,(cfg,line,'resident state differs')
    invalid=[w for w,(valid,kind,age) in enumerate(old) if not valid]
    if invalid:
     expected=invalid[0]
    else:
     stats['evictions']+=1
     delta=3-max(x[2] for x in old)
     if delta:stats['aged']+=1
     for x in state[set_]:x[2]=min(3,x[2]+delta)
     aged=state[set_]
     distant=[w for w,x in enumerate(aged) if x[2]==3]
     data=[w for w,x in enumerate(aged) if not x[1]]
     best=max(data,key=lambda w:aged[w][2]) if data else None
     expected=best if cfg['aware'] and best is not None and aged[best][2]>=3-cfg['bias'] else distant[0]
     stats['instruction_victims' if aged[expected][1] else 'data_victims']+=1
     if cfg['aware'] and best is not None and expected==best and any(aged[w][1] for w in distant):stats['protected_instruction']+=1
     category=('aged' if delta else 'no-aging')+('-instruction' if aged[expected][1] else '-data')
     if cfg['name'] in ('i1-h1-a1-b0','i1-h1-a1-b3','i2-h0-a0-b0') and sample_counts.get(category,0)<1:
      examples.append(dict(trace=trace.name,config=cfg['name'],event=stats['events'],before=old,after=[x[:] for x in aged],victim=selected,category=category));sample_counts[category]=1
    assert selected==expected,(cfg,line,'wrong victim',expected)
    assert [x[3] for x in reported]==[x[2] for x in state[set_]],(cfg,line,'wrong aging')
  rows.append(stats)
  with (OUT/'summary.csv').open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(stats));writer.writeheader();writer.writerows(rows)
  (OUT/'examples.json').write_text(json.dumps(examples,indent=2)+'\n')
  print(trace.name,cfg['name'],stats,flush=True)
print('All 90 event-sequence audits passed.',flush=True)
