def source_delta(before,after):
    def values(info):
        result={}
        for tier in info['tiered']['tiers']:
            for cf in tier.get('rocks',[]):
                for line in cf.get('database_statistics','').splitlines():
                    fields=line.split()
                    if len(fields)==4 and fields[1:3]==['COUNT',':']:
                        result[fields[0]]=int(fields[3])
        return result
    a,b=values(before['info']),values(after['info'])
    counters={}
    for source in ['memory','file','unknown']:
        counters[source]={}
        for unit in ['requests','bytes']:
            key='kuasar.chunk.'+source+'.'+unit
            assert key in a and key in b,'chunk source instrumentation missing'
            counters[source][unit]=b[key]-a[key]
    counters['origin']={unit:after['info']['tiered']['origin'][field]-before['info']['tiered']['origin'][field]
                       for unit,field in [('requests','chunk_hits'),('bytes','chunk_bytes')]}
    for unit in ['requests','bytes']:
        total=sum(v[unit] for v in counters.values())
        for v in counters.values():v[unit+'_percent']=100*v[unit]/total if total else None
    return {'categories':counters,'bytes_definition':'encoded encrypted chunk payload returned by the cache',
            'requests_definition':'successful chunk reads; repeated reads count repeatedly; zero and hole ranges require no chunk request',
            'file_definition':'RocksDB payload file read; not necessarily physical device IO',
            'scope':'before create through completion of first print command, before destruction',
            'unknown_definition':'inline payload with file IO that cannot be separated from index/filter IO'}
