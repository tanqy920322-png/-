import Link from "next/link";

export default function HomePage() {
  return (
    <main className="landing">
      <p className="kicker">金辉惠阳 · 展示区试点</p>
      <h1>先选风格，再定天花、地面与墙面</h1>
      <p className="lead">
        报价按示意单价即时计算。房间可以拖动旋转，换一套方案，地面、墙面和天花的材质会跟着变。
      </p>
      <div className="entry-grid">
        <Link href="/c/login" className="entry">
          <span>客户</span>
          <strong>开始选配</strong>
          <em>手机号登录，选项目和户型</em>
        </Link>
        <Link href="/admin/login" className="entry dark">
          <span>开发商</span>
          <strong>进入后台</strong>
          <em>发布项目、导入价表、查看一户一档</em>
        </Link>
      </div>
      <p className="fine">本地原型。部位报价不是合同价。测试验证码 123456。</p>
    </main>
  );
}
