def test_imports():
    import src.data.orderbook as ob
    from src.model.online import OnlineSGD
    assert hasattr(ob, "L2Book")
    m=OnlineSGD()
    m.partial_fit([{"spread_bps":1,"imb":0,"micro_dev":0,"vol":0,"ofi":0}],[0])
    p=m.predict_proba_up({"spread_bps":1,"imb":0,"micro_dev":0,"vol":0,"ofi":0})
    assert 0.0<=p<=1.0
