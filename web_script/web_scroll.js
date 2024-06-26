// ==UserScript==
// @name         武海笔院阅读器自动滚动翻页
// @namespace    http://tampermonkey.net/
// @version      2024-06-25
// @description  try to take over the world!
// @author       You
// @match        https://wqbook.wqxuetang.com/deep/read/pdf?bid=*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=wqxuetang.com
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function () {

    /** 当没有找到翻页元素时，需要进行重试检测 */
    const MAX_RETRY_COUNT = 3;

    /** 是否可以继续向下滚动。它是检测网页端是否已经加载了 6 张小图片来判断。
     * 其返回值有如下含义:
     * - continue: 可以继续向下滚动
     * - wait: 等待当前页加载完成
     * - error: 出现致命错误，需要暂停脚本
     * 
     * @returns 'continue' | 'wait' | 'error'
     */
    function can_continue() {
        // 首先获取当前所在的页数
        const page_num_elem = document.querySelector('.page-head-tol');
        if (!page_num_elem) {
            alert("没有找到记录当前页数的元素，请检查页面结构是否已经改动");
            return 'error';
        }
        // 其内容为类似 `8 / 99`
        const page_num = parseInt(page_num_elem.textContent.split('/')[0]);
        if (isNaN(page_num)) {
            alert("无法解析出当前的页数，请检查页面结构是否已经改动");
            return 'error';
        }
        // 查找该页对应的元素，看看它下面是否已经加载了 6 个小图片
        const img_count = document.querySelectorAll(`#pageImgBox${page_num} .page-lmg img`).length;
        if (img_count == 6) {
            return 'continue';
        } else if (img_count < 6) {
            return 'wait';
        } else {
            alert("发现有多余的小图片，请检查页面结构可能已经改动");
            return 'error';
        }
    }

    function create_btn() {
        if (document.querySelector('#auto_scroll_btn')) return;

        /** @type HTMLButtonElement */
        const btn = document.createElement('button');

        btn.id = "auto_scroll_btn";
        btn.textContent = '点我开始自动翻页';
        btn.style.cssText = `
            padding: 5px 10px;
            border-radius: 10px;
            border: 2px solid white;
            background-color: orange;

            position: absolute;
            left: 20%;
            top: 10px;
            z-index: 2233;
        `;

        return btn;
    }

    /** 
     * 找到滚动目标，并开始自动翻页，如果没有找到，会隔 1s 进行重试，最多重试 MAX_RETRY_COUNT 次
     * @param {number} retry_count 表示当前重试的次数
     */
    function init(retry_count = 0) {

        if (retry_count > MAX_RETRY_COUNT) {
            alert('未找到滚动元素，页面结构可能已经改动');
            return;
        }

        const scroll_target = document.querySelector('#scroll');

        if (!scroll_target) {
            // 1s 后继续进行尝试
            setTimeout(init, 1000, retry_count + 1);
            return;
        }

        const btn = create_btn();

        let is_auto_scroll = false;
        let interval_id = -1;
        /** 标记状态是否从 wait 到 continue 转变 */
        let flag_changed = false;

        btn.addEventListener('click', () => {
            if (is_auto_scroll) {
                // 取消自动翻页
                clearInterval(interval_id);
                btn.textContent = '点我开始自动翻页';
                btn.style.backgroundColor = 'orange';
                flag_changed = false;
            }
            else {
                // 开始自动翻页，3s 向下滚动 300px
                // 相比较 1s 滚动 100px 可以降低访问的频率
                interval_id = setInterval(() => {
                    // 有小数的情况，需要取整
                    const is_end = Math.ceil(scroll_target.scrollTop) >= Math.ceil(scroll_target.scrollHeight - scroll_target.clientHeight);
                    if (is_end) {
                        clearInterval(interval_id);
                        is_auto_scroll = false;
                        btn.textContent = '到底了，点我重新自动翻页';
                        btn.style.backgroundColor = 'yellowgreen';
                        return;
                    }

                    const flag = can_continue();
                    if (flag == 'wait') {
                        btn.textContent = '正在等待小图片加载，点我停止自动翻页';
                        flag_changed = true;
                        return;
                    }
                    if (flag == 'error') {
                        clearInterval(interval_id);
                        is_auto_scroll = false;
                        btn.textContent = '出现致命错误，脚本已无法工作';
                        btn.style.backgroundColor = 'grey';
                        btn.disabled = true;
                        return;
                    }
                    if (flag_changed) {
                        btn.textContent = '点我停止自动翻页';
                        flag_changed = false;
                    }

                    scroll_target.scrollTop += 300;
                }, 3000);
                btn.textContent = '点我停止自动翻页';
                btn.style.backgroundColor = 'orangered';
            }
            is_auto_scroll = !is_auto_scroll;
        });

        document.body.appendChild(btn);
    }

    window.addEventListener('load', () => { init() });
})();