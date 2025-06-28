import { useState } from 'react';
import PropTypes from 'prop-types';
import { useQuickReplies } from '../hooks/useQuickReplies';
import { useToast } from '../context/ToastContext';

const QuickReplyManager = ({ onClose }) => {
  const { replies, createReply, updateReply, deleteReply, isLoading } = useQuickReplies();
  const { showSuccess, showApiError } = useToast();
  const [editing, setEditing] = useState(null); // null or reply object
  const [form, setForm] = useState({ shortcut: '', content: '' });

  const startCreate = () => {
    setEditing(null);
    setForm({ shortcut: '', content: '' });
  };

  const startEdit = (reply) => {
    setEditing(reply);
    setForm({ shortcut: reply.shortcut, content: reply.content });
  };

  const handleChange = (e) => {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editing) {
        await updateReply({ id: editing.id, ...form });
        showSuccess('Quick reply updated');
      } else {
        await createReply(form);
        showSuccess('Quick reply created');
      }
      setEditing(null);
      setForm({ shortcut: '', content: '' });
    } catch (err) {
      showApiError(err);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this quick reply?')) return;
    try {
      await deleteReply(id);
      showSuccess('Quick reply deleted');
    } catch (err) {
      showApiError(err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg w-full max-w-lg p-6 overflow-y-auto max-h-[90vh]">
        <h2 className="text-xl font-semibold mb-4">Saved Replies</h2>
        <button className="absolute top-4 right-6 text-gray-600" onClick={onClose}>✕</button>

        {/* Form */}
        <form onSubmit={handleSubmit} className="mb-6">
          <div className="mb-2">
            <label className="block text-sm text-gray-700 mb-1">Shortcut</label>
            <input
              name="shortcut"
              value={form.shortcut}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>
          <div className="mb-2">
            <label className="block text-sm text-gray-700 mb-1">Content</label>
            <textarea
              name="content"
              value={form.content}
              onChange={handleChange}
              className="w-full border rounded px-3 py-2"
              required
            />
          </div>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">
            {editing ? 'Update' : 'Create'}
          </button>
        </form>

        {/* List */}
        {isLoading ? (
          <p>Loading…</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left border-b">
                <th className="py-2">Shortcut</th>
                <th className="py-2">Content</th>
                <th className="py-2 w-20">Actions</th>
              </tr>
            </thead>
            <tbody>
              {replies.map((r) => (
                <tr key={r.id} className="border-b">
                  <td className="py-1">{r.shortcut}</td>
                  <td className="py-1">{r.content}</td>
                  <td className="py-1 space-x-1">
                    <button onClick={() => startEdit(r)} className="text-blue-600">Edit</button>
                    <button onClick={() => handleDelete(r.id)} className="text-red-600">Del</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

QuickReplyManager.propTypes = {
  onClose: PropTypes.func.isRequired,
};

export default QuickReplyManager;
