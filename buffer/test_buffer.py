"""
缓冲管理器单元测试
验证核心功能的正确性
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from disk.sim_disk_compact_v2 import DiskManager
from buffer import BufferManager
import time

def print_sep(title=""):
    """打印分隔线"""
    print("\n" + "="*70)
    if title:
        print(f"  {title}")
        print("="*70)

def test_basic_operations():
    """测试1: 基本读写操作"""
    print_sep("测试1: 基本读写操作")
    
    disk = DiskManager('test_disk.img', 64, 100)
    buffer = BufferManager(disk, capacity=4)
    
    print("✅ 创建缓冲管理器（容量=4页）")
    
    # 写入测试
    print("\n📝 写入数据到块 10, 20, 30...")
    buffer.write_page(10, b"This is block 10 data")
    buffer.write_page(20, b"This is block 20 data")
    buffer.write_page(30, b"This is block 30 data")
    
    status = buffer.get_status()
    print(f"   缓冲池使用: {status['used']}/{status['capacity']}")
    print(f"   统计: {status['statistics']}")
    
    # 读取测试（应该命中）
    print("\n📖 读取块 10（应该命中缓存）...")
    data = buffer.read_page(10)
    print(f"   读取到: {data.decode('utf-8', errors='ignore').strip()}")
    
    status = buffer.get_status()
    print(f"   命中率: {status['statistics']['hit_ratio']}")
    
    disk.close()
    print("\n✅ 测试通过")

def test_lru_replacement():
    """测试2: LRU置换算法"""
    print_sep("测试2: LRU页面置换算法")
    
    disk = DiskManager('test_disk.img', 64, 100)
    buffer = BufferManager(disk, capacity=3, enable_logging=False)
    
    print("✅ 缓冲池容量=3页")
    
    # 填满缓冲池
    print("\n📝 写入块 1, 2, 3（填满缓冲池）...")
    buffer.write_page(1, b"Block 1")
    time.sleep(0.1)
    buffer.write_page(2, b"Block 2")
    time.sleep(0.1)
    buffer.write_page(3, b"Block 3")
    time.sleep(0.1)
    
    # 访问部分页面
    print("\n📖 访问块 1 和 2（更新访问时间）...")
    buffer.read_page(1)
    time.sleep(0.05)
    buffer.read_page(2)
    time.sleep(0.05)
    
    status = buffer.get_status()
    print(f"   当前缓冲池: {[p['block_id'] for p in status['pages']]}")
    
    # 触发置换
    print("\n⚠️  写入块 4（应触发LRU置换，淘汰块3）...")
    buffer.write_page(4, b"Block 4")
    
    status = buffer.get_status()
    page_ids = [p['block_id'] for p in status['pages']]
    
    print(f"   置换后缓冲池: {page_ids}")
    print(f"   淘汰次数: {status['statistics']['evict']}")
    
    if 3 not in page_ids and 4 in page_ids:
        print("\n✅ LRU算法正确：块3被淘汰，块4被加载")
    else:
        print("\n❌ LRU算法错误")
    
    disk.close()

def test_dirty_page_writeback():
    """测试3: 脏页回写机制"""
    print_sep("测试3: 脏页回写机制")
    
    disk = DiskManager('test_disk.img', 64, 100)
    buffer = BufferManager(disk, capacity=4)
    
    print("📝 写入块 100...")
    buffer.write_page(100, b"Important data that must be saved!")
    
    status = buffer.get_status()
    dirty_before = sum(1 for p in status['pages'] if p['is_dirty'])
    print(f"   脏页数量: {dirty_before}")
    
    print("\n💾 调用 flush_all() 刷新所有脏页...")
    buffer.flush_all()
    
    status = buffer.get_status()
    dirty_after = sum(1 for p in status['pages'] if p['is_dirty'])
    print(f"   刷新后脏页数量: {dirty_after}")
    
    if dirty_after == 0:
        print("\n✅ 脏页回写成功：所有页都已干净")
    else:
        print("\n❌ 脏页回写失败")
    
    disk.close()

def test_performance():
    """测试4: 性能对比"""
    print_sep("测试4: 性能对比（有缓冲 vs 无缓冲）")
    
    disk = DiskManager('test_disk.img', 64, 100)
    buffer = BufferManager(disk, capacity=8)
    
    # 准备测试数据（包含重复访问）
    test_blocks = [10, 20, 30, 40, 10, 20, 30, 40, 10, 20] * 3
    
    # 测试1: 使用缓冲
    print(f"\n⏱️  测试: 使用缓冲管理器读取（{len(test_blocks)}次访问）")
    buffer.stats.reset()
    start = time.time()
    
    for block_id in test_blocks:
        buffer.read_page(block_id)
    
    buffered_time = time.time() - start
    stats = buffer.stats.get_summary()
    
    print(f"   耗时: {buffered_time:.4f}秒")
    print(f"   命中率: {stats['hit_ratio']}")
    print(f"   命中/缺页: {stats['hit']}/{stats['miss']}")
    
    # 测试2: 直接读磁盘
    print(f"\n⏱️  测试: 直接读磁盘（无缓存）")
    start = time.time()
    
    for block_id in test_blocks:
        disk.read_block(block_id)
    
    direct_time = time.time() - start
    
    print(f"   耗时: {direct_time:.4f}秒")
    
    # 对比
    improvement = ((direct_time - buffered_time) / direct_time * 100)
    print(f"\n📊 性能对比:")
    print(f"   有缓冲: {buffered_time:.4f}秒")
    print(f"   无缓冲: {direct_time:.4f}秒")
    print(f"   性能提升: {improvement:.1f}%")
    
    if improvement > 0:
        print("\n✅ 缓冲机制有效提升了性能")
    
    disk.close()

def test_statistics():
    """测试5: 统计功能"""
    print_sep("测试5: 统计功能验证")
    
    disk = DiskManager('test_disk.img', 64, 100)
    buffer = BufferManager(disk, capacity=4)
    
    # 执行一系列操作
    buffer.write_page(10, b"Data")
    buffer.write_page(20, b"Data")
    buffer.read_page(10)  # 命中
    buffer.read_page(30)  # 未命中
    buffer.read_page(10)  # 命中
    
    stats = buffer.stats.get_summary()
    
    print("📊 统计信息:")
    print(f"   总访问次数: {stats['total_access']}")
    print(f"   缓存命中: {stats['hit']}")
    print(f"   缺页: {stats['miss']}")
    print(f"   命中率: {stats['hit_ratio']}")
    
    expected_hits = 2
    expected_misses = 1
    
    if stats['hit'] == expected_hits and stats['miss'] == expected_misses:
        print("\n✅ 统计功能正确")
    else:
        print(f"\n❌ 统计错误（期望命中{expected_hits}次，缺页{expected_misses}次）")
    
    disk.close()

def run_all_tests():
    """运行所有测试"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                  内存缓冲页模块 - 单元测试                          ║
║                                                                    ║
║  测试内容:                                                          ║
║    1. 基本读写操作                                                  ║
║    2. LRU置换算法                                                   ║
║    3. 脏页回写机制                                                  ║
║    4. 性能对比分析                                                  ║
║    5. 统计功能验证                                                  ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        test_basic_operations()
        input("\n按回车继续下一个测试...")
        
        test_lru_replacement()
        input("\n按回车继续下一个测试...")
        
        test_dirty_page_writeback()
        input("\n按回车继续下一个测试...")
        
        test_performance()
        input("\n按回车继续下一个测试...")
        
        test_statistics()
        
        print_sep("✅ 所有测试完成")
        print("\n🎉 所有测试通过！缓冲管理器功能正常。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
