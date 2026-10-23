/* Shared department permissions; no changes are saved until explicitly submitted. */
(() => {
    const labels = {dashboard: 'Дашборд', selection: 'Подбор объектов', worker_status: 'Вахтовики', reports: 'Отчёты', payroll: 'Расчёт зп', admin: 'Админ-панель'};
    let data;
    const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    async function api(path = '', method = 'GET', body) {
        const response = await fetch('/api/departments' + path, {method, headers: {'Content-Type': 'application/json'}, credentials: 'same-origin', body: body ? JSON.stringify(body) : undefined});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Не удалось сохранить настройки');
        return result;
    }
    function fail(error) { showNotification(error.message, 'error'); }
    function addSearch(list, placeholder) {
        if (!list) return;
        const input = document.createElement('input');
        input.type = 'search';
        input.className = 'department-search';
        input.placeholder = placeholder;
        input.setAttribute('aria-label', placeholder);
        const empty = document.createElement('p');
        empty.className = 'department-empty';
        empty.textContent = 'Ничего не найдено';
        empty.hidden = true;
        list.before(input);
        list.after(empty);
        input.addEventListener('input', () => {
            const query = input.value.trim().toLocaleLowerCase('ru');
            let found = 0;
            [...list.children].forEach(row => {
                row.hidden = !row.textContent.toLocaleLowerCase('ru').includes(query);
                if (!row.hidden) found++;
            });
            empty.hidden = found > 0;
        });
        return input;
    }
    window.openDepartmentUser = async function (id) {
        document.getElementById('userModal').style.display = 'none';
        document.querySelectorAll('.admin-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'departments'));
        document.querySelectorAll('.admin-tab-content').forEach(t => t.classList.toggle('active', t.id === 'tab-departments'));
        await window.loadDepartments();
        const select = document.getElementById('departmentUser');
        if (select && id) { select.value = id; await renderUser(); }
    };
    function choices(value) {
        return [['inherit','Как у отдела'], ['allow','Разрешить'], ['deny','Запретить']].map(([v,l]) => `<option value="${v}" ${value === v ? 'selected' : ''}>${l}</option>`).join('');
    }
    const state = value => value === true ? 'allow' : value === false ? 'deny' : 'inherit';
    window.loadDepartments = async function () {
        const root = document.getElementById('departmentsContent');
        root.textContent = 'Загрузка…';
        try {
            data = await api();
            root.innerHTML = `<div class="permissions-section"><h3>Настройки отдела</h3>
                <label class="department-field" for="departmentSelect">Выберите отдел</label><select id="departmentSelect"><option value="">Создать новый отдел</option>${data.departments.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('')}</select>
                <form id="departmentForm"><div id="departmentFields"></div><button class="btn-small" type="submit">Сохранить отдел</button></form></div>
                <div class="permissions-section"><h3>Сотрудники отдела</h3><div id="departmentRoster"></div></div>
                <div class="permissions-section"><h3>Без отдела</h3><p>Эти сотрудники сохраняют прежние индивидуальные доступы до назначения отдела.</p><div id="departmentUnassigned"></div></div>
                <div class="permissions-section department-exceptions"><h3>Доступ сотрудника</h3><p>Сотрудники без отдела сохраняют прежние индивидуальные права.</p>
                <label class="department-field" for="departmentUser">Сотрудник</label>
                <select id="departmentUser"><option value="">Выберите сотрудника</option>${data.users.map(u => `<option value="${u.id}">${esc(u.name)}</option>`).join('')}</select>
                <div id="departmentUserFields"></div></div>`;
            document.getElementById('departmentSelect').addEventListener('change', renderDepartment);
            document.getElementById('departmentForm').addEventListener('submit', saveDepartment);
            document.getElementById('departmentUser').addEventListener('change', renderUser);
            renderDepartment();
            renderUnassigned();
        } catch (e) { root.textContent = e.message; }
    };
    function renderDepartment() {
        const id = Number(document.getElementById('departmentSelect').value);
        renderRoster(id);
        const d = data.departments.find(d => d.id === id) || {name:'',modules:{},objects:{}};
        document.getElementById('departmentFields').innerHTML = `<label class="department-field" for="departmentName">Название отдела</label><input id="departmentName" placeholder="Например, Подбор" required maxlength="100" value="${esc(d.name)}">
            <h4>Разделы</h4><p>Доступ к админ-панели не меняет роль и полномочия сотрудника.</p>
            <div class="department-modules">${Object.entries(labels).map(([k,l]) => `<label class="perm-checkbox"><input type="checkbox" data-dept-module="${k}" ${d.modules[k] ? 'checked' : ''}>${l}</label>`).join('')}</div>
            <h4>Объекты в подборе</h4><label><input type="checkbox" id="departmentAllObjects" ${d.all_objects ? 'checked' : ''}>Все объекты, включая новые</label>
            <div class="objects-perms-list" id="departmentObjectList">${data.objects.map(o => `<label class="object-perm-item"><input type="checkbox" data-dept-object="${o.id}" ${d.objects[o.id] ? 'checked' : ''}>${esc(o.name)}</label>`).join('')}</div>`;
        const objectSearch = addSearch(document.getElementById('departmentObjectList'), 'Поиск объекта');
        const toggle = () => {
            const all = document.getElementById('departmentAllObjects').checked;
            document.getElementById('departmentObjectList').hidden = all;
            objectSearch.hidden = all;
            if (all) objectSearch.nextElementSibling.nextElementSibling.hidden = true;
            else objectSearch.dispatchEvent(new Event('input'));
        };
        document.getElementById('departmentAllObjects').addEventListener('change', toggle);
        toggle();
    }
    function renderRoster(id) {
        const root = document.getElementById('departmentRoster');
        const department = data.departments.find(d => d.id === id);
        if (!department) {
            root.innerHTML = '<p class="department-empty">Выберите сохранённый отдел, чтобы увидеть его сотрудников.</p>';
            return;
        }
        const members = data.users.filter(u => u.department_id === id).sort((a,b) => a.name.localeCompare(b.name, 'ru'));
        const candidates = data.users.filter(u => u.department_id !== id).sort((a,b) => a.name.localeCompare(b.name, 'ru'));
        root.innerHTML = `<div class="department-roster-heading"><strong>${esc(department.name)}</strong><span class="department-count">Сотрудников: ${members.length}</span></div>
            ${members.length ? `<ul class="objects-perms-list department-roster-list" id="departmentCurrentMembers">${members.map(u => `<li class="object-perm-item"><span class="department-person">${esc(u.name)}</span><button type="button" class="department-remove" data-remove-member="${u.id}" aria-label="Убрать из отдела: ${esc(u.name)}">Убрать из отдела</button></li>`).join('')}</ul>` : '<p class="department-empty">В этом отделе пока нет сотрудников.</p>'}
            <button type="button" class="btn-small" id="departmentAddToggle" aria-expanded="false" aria-controls="departmentAddPanel">Добавить сотрудников</button>
            <div id="departmentAddPanel" hidden>
                <p>Отметьте сотрудников для отдела «${esc(department.name)}». Если сотрудник уже в другом отделе, он будет переведён.</p>
                ${candidates.length ? `<div class="objects-perms-list" id="departmentMembersList">${candidates.map(u => `<label class="object-perm-item"><input type="checkbox" name="departmentMember" value="${u.id}"><span class="department-person">${esc(u.name)}<small>${esc(data.departments.find(d => d.id === u.department_id)?.name || 'Без отдела')}</small></span></label>`).join('')}</div>
                <p>Сотрудники без отдела получат права этого отдела. При переводе из другого отдела текущие доступы сохранятся. Личные исключения можно настроить позже.</p>
                <button type="button" class="btn-small" id="departmentAssign">Назначить выбранных</button>` : '<p class="department-empty">Все доступные сотрудники уже в этом отделе.</p>'}
            </div>`;
        addSearch(document.getElementById('departmentCurrentMembers'), 'Поиск в составе отдела');
        root.querySelectorAll('[data-remove-member]').forEach(button => {
            button.addEventListener('click', () => removeMember(Number(button.dataset.removeMember), id, button));
        });
        addSearch(document.getElementById('departmentMembersList'), 'Поиск сотрудника или отдела');
        document.getElementById('departmentAssign')?.addEventListener('click', assignMembers);
        document.getElementById('departmentAddToggle').addEventListener('click', event => {
            const panel = document.getElementById('departmentAddPanel');
            panel.hidden = !panel.hidden;
            event.currentTarget.setAttribute('aria-expanded', String(!panel.hidden));
            event.currentTarget.textContent = panel.hidden ? 'Добавить сотрудников' : 'Скрыть добавление';
        });
    }
    function renderUnassigned() {
        const root = document.getElementById('departmentUnassigned');
        const users = data.users.filter(user => user.department_id === null)
            .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
        root.innerHTML = `<p>Сотрудников без отдела: ${users.length}</p><ul class="objects-perms-list department-roster-list" id="departmentUnassignedList">${users.map(user => `<li class="object-perm-item"><button type="button" class="department-user-link" data-open-user="${user.id}">${esc(user.name)}</button><small>${user.legacy ? 'Старые индивидуальные права' : 'Личные настройки'}</small></li>`).join('')}</ul>`;
        addSearch(document.getElementById('departmentUnassignedList'), 'Поиск сотрудника без отдела');
        root.querySelectorAll('[data-open-user]').forEach(button => button.addEventListener('click', async () => {
            document.getElementById('departmentUser').value = button.dataset.openUser;
            await renderUser();
            document.getElementById('departmentUser').scrollIntoView({behavior:'smooth', block:'center'});
        }));
    }
    async function saveDepartment(event) {
        event.preventDefault();
        const id = document.getElementById('departmentSelect').value;
        const body = {name: document.getElementById('departmentName').value, modules:{}, objects:{}, all_objects:document.getElementById('departmentAllObjects').checked};
        document.querySelectorAll('[data-dept-module]').forEach(el => body.modules[el.dataset.deptModule] = el.checked);
        if (!body.all_objects) document.querySelectorAll('[data-dept-object]').forEach(el => body.objects[el.dataset.deptObject] = el.checked);
        if (id && !confirm('Изменить права отдела? Они применятся ко всем его сотрудникам, кроме личных исключений.')) return;
        try {
            const result = await api(id ? '/' + id : '', id ? 'PUT' : 'POST', body);
            await loadDepartments();
            document.getElementById('departmentSelect').value = result.id;
            renderDepartment();
            showNotification('Отдел сохранён', 'success');
        } catch(e) { fail(e); }
    }
    async function removeMember(userId, departmentId, button) {
        const user = data.users.find(u => u.id === userId);
        if (!user || !confirm(`Убрать сотрудника «${user.name}» из отдела?\n\nАккаунт не удаляется. Текущие доступы сохранятся как личные настройки и больше не будут зависеть от этого отдела.`)) return;
        button.disabled = true;
        try {
            await api('/assign', 'POST', {department_id:null, user_ids:[userId], mode:'preserve'});
            await loadDepartments();
            document.getElementById('departmentSelect').value = departmentId;
            renderDepartment();
            showNotification('Сотрудник убран из отдела. Текущие доступы сохранены.', 'success');
        } catch(e) { fail(e); }
        finally { button.disabled = false; }
    }
    async function assignMembers() {
        const id = Number(document.getElementById('departmentSelect').value);
        const ids = [...document.querySelectorAll('[name=departmentMember]:checked')].map(el => Number(el.value));
        if (!id || !ids.length) return fail(new Error('Выберите сохранённый отдел и сотрудников'));
        const inheriting = ids.filter(uid => data.users.find(user => user.id === uid)?.department_id === null).length;
        const preserving = ids.length - inheriting;
        const details = [inheriting ? `Без отдела: ${inheriting} — получат права отдела.` : '', preserving ? `Из других отделов: ${preserving} — сохранят текущие права.` : ''].filter(Boolean).join('\n');
        if (!confirm(`Назначить отдел ${ids.length} сотрудникам?\n\n${details}`)) return;
        try {
            await api('/assign', 'POST', {department_id:id, user_ids:ids, mode:'preserve'});
            await loadDepartments();
            document.getElementById('departmentSelect').value = id;
            renderDepartment();
            showNotification('Сотрудники назначены в отдел', 'success');
        } catch(e) { fail(e); }
    }
    async function renderUser() {
        const id = document.getElementById('departmentUser').value;
        const root = document.getElementById('departmentUserFields');
        root.textContent = '';
        if (!id) return;
        try {
            const u = await api('/users/' + id);
            if (document.getElementById('departmentUser').value !== id) return;
            const legacy = u.legacy;
            root.innerHTML = `<p>Отдел: ${esc(data.departments.find(d => d.id === u.department_id)?.name || 'Без отдела — индивидуальные доступы')}</p><p>${legacy ? 'Действуют прежние индивидуальные права. Открытие этой карточки их не меняет.' : 'Личные исключения важнее общих прав отдела.'}</p><form id="departmentOverrides">
                <h4>Доступ к разделам</h4>${Object.entries(labels).map(([k,l]) => `<label class="object-perm-item department-rule"><span>${l}</span><select data-user-module="${k}" ${legacy && k === 'admin' ? 'disabled' : ''}>${legacy ? `<option value="allow" ${u.effective[0][k] ? 'selected' : ''}>Разрешить</option><option value="deny" ${!u.effective[0][k] ? 'selected' : ''}>Запретить</option>` : choices(state(u.overrides.modules[k]))}</select><span class="department-status">Сейчас: ${u.effective[0][k] ? 'разрешено' : 'запрещено'}</span></label>`).join('')}
                <h4>Объекты в подборе</h4><div class="objects-perms-list" id="departmentExceptionObjects">${data.objects.map(o => `<label class="object-perm-item department-rule"><span>${esc(o.name)}</span><select data-user-object="${o.id}">${legacy ? `<option value="allow" ${u.effective[1][o.id]?.selection ? 'selected' : ''}>Разрешить</option><option value="deny" ${!u.effective[1][o.id]?.selection ? 'selected' : ''}>Запретить</option>` : choices(state(u.overrides.objects[o.id]))}</select><span class="department-status">Сейчас: ${u.effective[0].selection && u.effective[1][o.id]?.selection ? 'разрешено' : 'запрещено'}</span></label>`).join('')}</div>
                <button type="submit" class="btn-small">${legacy ? 'Сохранить индивидуальные права' : 'Сохранить исключения'}</button></form>`;
            addSearch(document.getElementById('departmentExceptionObjects'), 'Поиск объекта для исключения');
            document.getElementById('departmentOverrides').addEventListener('submit', async event => {
                event.preventDefault();
                const body = {modules:{},objects:{}};
                document.querySelectorAll('[data-user-module]').forEach(el => { if(el.value !== 'inherit') body.modules[el.dataset.userModule] = el.value === 'allow'; });
                if (legacy) body.modules.admin = u.effective[0].admin;
                document.querySelectorAll('[data-user-object]').forEach(el => { if(el.value !== 'inherit') body.objects[el.dataset.userObject] = el.value === 'allow'; });
                try { await api('/users/' + id, 'PUT', body); await renderUser(); showNotification('Исключения сохранены', 'success'); } catch(e) { fail(e); }
            });
        } catch(e) { root.textContent = e.message; }
    }
})();
