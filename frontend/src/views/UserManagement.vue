<template>
  <div class="space-y-6">
    <el-tabs v-model="activeTab" type="border-card">

      <!-- ══ Tab 1: 用户管理 ══════════════════════════════════════════ -->
      <el-tab-pane label="用户管理" name="users">
        <div class="flex justify-end mb-4">
          <el-button type="primary" @click="openCreateUserDialog">新建用户</el-button>
        </div>

        <el-table :data="users" v-loading="loadingUsers" stripe>
          <el-table-column prop="id" label="ID" width="64" />
          <el-table-column prop="username" label="用户名" min-width="120" />

          <el-table-column label="角色" width="180">
            <template #default="{ row }">
              <el-select
                v-model="row.role"
                size="small"
                :disabled="row.username === selfUsername"
                @change="handleRoleChange(row)"
              >
                <el-option
                  v-for="r in roles"
                  :key="r.name"
                  :label="r.display_name"
                  :value="r.name"
                />
              </el-select>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-switch
                v-model="row.is_active"
                :disabled="row.username === selfUsername"
                @change="handleStatusChange(row)"
              />
            </template>
          </el-table-column>

          <el-table-column label="创建时间" min-width="160">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>

          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text @click="openResetPwdDialog(row)">改密码</el-button>
              <el-button
                size="small" text type="danger"
                :disabled="row.username === selfUsername"
                @click="handleDeleteUser(row)"
              >删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ══ Tab 2: 角色管理 ══════════════════════════════════════════ -->
      <el-tab-pane label="角色管理" name="roles">
        <div class="flex justify-end mb-4">
          <el-button type="primary" @click="openCreateRoleDialog">新建角色</el-button>
        </div>

        <el-table :data="roles" v-loading="loadingRoles" stripe>
          <el-table-column prop="name" label="角色标识" width="140" />
          <el-table-column prop="display_name" label="显示名称" width="140" />

          <el-table-column label="可访问模块">
            <template #default="{ row }">
              <div class="flex flex-wrap gap-1">
                <el-tag
                  v-for="key in row.module_keys"
                  :key="key"
                  size="small"
                  :type="row.name === 'admin' ? 'warning' : 'info'"
                >
                  {{ MODULE_LABELS[key] || key }}
                </el-tag>
                <span v-if="!row.module_keys.length" class="text-gray-400 text-xs">无访问权限</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_system ? 'danger' : 'success'">
                {{ row.is_system ? '系统内置' : '自定义' }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small" text
                :disabled="row.name === 'admin'"
                @click="openEditRoleDialog(row)"
              >编辑权限</el-button>
              <el-button
                size="small" text type="danger"
                :disabled="row.is_system"
                @click="handleDeleteRole(row)"
              >删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ── 新建用户 dialog ──────────────────────────────────────── -->
    <el-dialog v-model="createUserVisible" title="新建用户" width="420px" destroy-on-close>
      <el-form ref="createUserFormRef" :model="createUserForm" :rules="createUserRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createUserForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createUserForm.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createUserForm.role" style="width:100%">
            <el-option v-for="r in roles" :key="r.name" :label="r.display_name" :value="r.name" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createUserVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreateUser">创建</el-button>
      </template>
    </el-dialog>

    <!-- ── 重置密码 dialog ─────────────────────────────────────── -->
    <el-dialog v-model="resetPwdVisible" :title="`重置密码 · ${resetTarget?.username}`" width="420px" destroy-on-close>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-width="80px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="resetForm.password" type="password" show-password placeholder="至少6位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetPwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitResetPwd">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- ── 新建/编辑角色 dialog ────────────────────────────────── -->
    <el-dialog
      v-model="roleDialogVisible"
      :title="roleDialogMode === 'create' ? '新建角色' : `编辑角色权限 · ${editingRole?.display_name}`"
      width="520px"
      destroy-on-close
    >
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="90px">
        <template v-if="roleDialogMode === 'create'">
          <el-form-item label="角色标识" prop="name">
            <el-input v-model="roleForm.name" placeholder="英文小写，如 operator" />
          </el-form-item>
          <el-form-item label="显示名称" prop="display_name">
            <el-input v-model="roleForm.display_name" placeholder="如 操作员" />
          </el-form-item>
        </template>

        <el-form-item label="可访问模块" prop="module_keys">
          <div class="w-full">
            <div class="flex items-center gap-3 mb-3">
              <el-checkbox
                :model-value="roleForm.module_keys.length === ALL_MODULES.length"
                :indeterminate="roleForm.module_keys.length > 0 && roleForm.module_keys.length < ALL_MODULES.length"
                @change="toggleAllModules"
              >全选</el-checkbox>
            </div>
            <div class="grid grid-cols-2 gap-2">
              <el-checkbox
                v-for="mod in ALL_MODULES"
                :key="mod.key"
                :model-value="roleForm.module_keys.includes(mod.key)"
                @change="(checked) => toggleModule(mod.key, checked)"
              >
                {{ mod.label }}
              </el-checkbox>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRoleDialog">
          {{ roleDialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listUsers, createUser, updateUser, deleteUser } from "../api/users";
import { listRoles, createRole, updateRole, deleteRole } from "../api/roles";
import { useAuthStore } from "../store/modules/auth";

// ── Constants ─────────────────────────────────────────────────────
const ALL_MODULES = [
  { key: "console",         label: "控制台" },
  { key: "tasks",           label: "任务管理" },
  { key: "configs",         label: "配置模板" },
  { key: "materials",       label: "素材库" },
  { key: "source_videos",   label: "源视频库" },
  { key: "rough_cut",       label: "混剪单元" },
  { key: "audit",           label: "操作历史" },
  { key: "user_management", label: "权限控制" },
  { key: "settings",        label: "系统设置" },
];
const MODULE_LABELS = Object.fromEntries(ALL_MODULES.map((m) => [m.key, m.label]));

// ── State ──────────────────────────────────────────────────────────
const authStore = useAuthStore();
const selfUsername = authStore.username;
const activeTab = ref("users");
const submitting = ref(false);

// Users
const users = ref([]);
const loadingUsers = ref(false);

// Roles
const roles = ref([]);
const loadingRoles = ref(false);

// ── Data fetching ──────────────────────────────────────────────────
async function fetchUsers() {
  loadingUsers.value = true;
  try {
    const res = await listUsers();
    users.value = res.data;
  } finally {
    loadingUsers.value = false;
  }
}

async function fetchRoles() {
  loadingRoles.value = true;
  try {
    const res = await listRoles();
    roles.value = res.data;
  } finally {
    loadingRoles.value = false;
  }
}

onMounted(() => Promise.all([fetchUsers(), fetchRoles()]));

// ── User: role / status / delete ──────────────────────────────────
async function handleRoleChange(row) {
  try {
    await updateUser(row.id, { role: row.role });
    ElMessage.success("角色已更新");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "更新失败");
    fetchUsers();
  }
}

async function handleStatusChange(row) {
  try {
    await updateUser(row.id, { is_active: row.is_active });
    ElMessage.success(row.is_active ? "账号已启用" : "账号已禁用");
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "更新失败");
    fetchUsers();
  }
}

async function handleDeleteUser(row) {
  await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    confirmButtonClass: "el-button--danger",
  });
  try {
    await deleteUser(row.id);
    ElMessage.success("已删除");
    fetchUsers();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

// ── User: create dialog ───────────────────────────────────────────
const createUserVisible = ref(false);
const createUserFormRef = ref(null);
const createUserForm = reactive({ username: "", password: "", role: "user" });
const createUserRules = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, min: 6, message: "密码至少6位", trigger: "blur" }],
  role: [{ required: true }],
};

function openCreateUserDialog() {
  createUserForm.username = "";
  createUserForm.password = "";
  createUserForm.role = "user";
  createUserVisible.value = true;
}

async function submitCreateUser() {
  await createUserFormRef.value?.validate();
  submitting.value = true;
  try {
    await createUser({ ...createUserForm });
    ElMessage.success("用户创建成功");
    createUserVisible.value = false;
    fetchUsers();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  } finally {
    submitting.value = false;
  }
}

// ── User: reset password dialog ───────────────────────────────────
const resetPwdVisible = ref(false);
const resetFormRef = ref(null);
const resetTarget = ref(null);
const resetForm = reactive({ password: "" });
const resetRules = {
  password: [{ required: true, min: 6, message: "密码至少6位", trigger: "blur" }],
};

function openResetPwdDialog(row) {
  resetTarget.value = row;
  resetForm.password = "";
  resetPwdVisible.value = true;
}

async function submitResetPwd() {
  await resetFormRef.value?.validate();
  submitting.value = true;
  try {
    await updateUser(resetTarget.value.id, { new_password: resetForm.password });
    ElMessage.success("密码已修改");
    resetPwdVisible.value = false;
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "修改失败");
  } finally {
    submitting.value = false;
  }
}

// ── Role: create / edit dialog ────────────────────────────────────
const roleDialogVisible = ref(false);
const roleDialogMode = ref("create"); // "create" | "edit"
const editingRole = ref(null);
const roleFormRef = ref(null);
const roleForm = reactive({ name: "", display_name: "", module_keys: [] });
const roleRules = {
  name: [
    { required: true, message: "请输入角色标识", trigger: "blur" },
    { pattern: /^[a-z0-9_]+$/, message: "只能包含小写字母、数字和下划线", trigger: "blur" },
  ],
  display_name: [{ required: true, message: "请输入显示名称", trigger: "blur" }],
};

function openCreateRoleDialog() {
  roleDialogMode.value = "create";
  editingRole.value = null;
  roleForm.name = "";
  roleForm.display_name = "";
  roleForm.module_keys = [];
  roleDialogVisible.value = true;
}

function openEditRoleDialog(row) {
  roleDialogMode.value = "edit";
  editingRole.value = row;
  roleForm.name = row.name;
  roleForm.display_name = row.display_name;
  roleForm.module_keys = [...row.module_keys];
  roleDialogVisible.value = true;
}

function toggleModule(key, checked) {
  if (checked) {
    if (!roleForm.module_keys.includes(key)) roleForm.module_keys.push(key);
  } else {
    roleForm.module_keys = roleForm.module_keys.filter((k) => k !== key);
  }
}

function toggleAllModules(checked) {
  roleForm.module_keys = checked ? ALL_MODULES.map((m) => m.key) : [];
}

async function submitRoleDialog() {
  await roleFormRef.value?.validate();
  submitting.value = true;
  try {
    if (roleDialogMode.value === "create") {
      await createRole({
        name: roleForm.name,
        display_name: roleForm.display_name,
        module_keys: roleForm.module_keys,
      });
      ElMessage.success("角色创建成功");
    } else {
      await updateRole(editingRole.value.id, {
        module_keys: roleForm.module_keys,
      });
      ElMessage.success("角色权限已更新");
    }
    roleDialogVisible.value = false;
    fetchRoles();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "操作失败");
  } finally {
    submitting.value = false;
  }
}

async function handleDeleteRole(row) {
  await ElMessageBox.confirm(`确认删除角色「${row.display_name}」？已分配该角色的用户将失去对应权限。`, "删除确认", {
    type: "warning",
    confirmButtonText: "删除",
    confirmButtonClass: "el-button--danger",
  });
  try {
    await deleteRole(row.id);
    ElMessage.success("已删除");
    fetchRoles();
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

// ── Helpers ───────────────────────────────────────────────────────
function formatDate(dt) {
  if (!dt) return "-";
  return new Date(dt).toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}
</script>
